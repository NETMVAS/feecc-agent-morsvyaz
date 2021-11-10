from __future__ import annotations

import typing as tp
from pathlib import Path

from loguru import logger

from .Camera import Camera
from .Employee import Employee
from .IO_gateway import generate_qr_code, post_to_datalog, print_image, publish_file
from .Singleton import SingletonMeta
from .Types import AdditionalInfo
from .Unit import Unit
from ._image_generation import create_seal_tag
from .config import config
from .database import MongoDbWrapper
from .exceptions import StateForbiddenError
from .models import ProductionSchema
from .states import (
    AUTHORIZED_IDLING_STATE,
    AWAIT_LOGIN_STATE,
    GATHER_COMPONENTS_STATE,
    PRODUCTION_STAGE_ONGOING_STATE,
    STATE_TRANSITION_MAP,
    State,
    UNIT_ASSIGNED_IDLING_STATE,
)


class WorkBench(metaclass=SingletonMeta):
    """
    Work bench is a union of an Employee, working at it and Camera attached.
    It provides highly abstract interface for interaction with them
    """

    @logger.catch
    def __init__(self) -> None:
        self._database: MongoDbWrapper = MongoDbWrapper()
        self.number: int = config.workbench_config.number
        camera_number: tp.Optional[int] = config.hardware.camera_no
        self.camera: tp.Optional[Camera] = (
            Camera(camera_number) if camera_number and not config.feecc_io_gateway.autonomous_mode else None
        )
        self.employee: tp.Optional[Employee] = None
        self.unit: tp.Optional[Unit] = None
        self.state: State = AWAIT_LOGIN_STATE

        logger.info(f"Workbench {self.number} was initialized")

    async def create_new_unit(self, schema: ProductionSchema) -> Unit:
        """initialize a new instance of the Unit class"""
        if self.state is not AUTHORIZED_IDLING_STATE:
            raise StateForbiddenError("Cannot create a new unit unless workbench has state AuthorizedIdling")

        unit = Unit(schema)
        await self._database.upload_unit(unit)

        if config.printer.print_barcode and not config.feecc_io_gateway.autonomous_mode:
            if unit.schema.parent_schema_id is None:
                annotation = unit.schema.unit_name
            else:
                parent_schema = await self._database.get_schema_by_id(unit.schema.parent_schema_id)
                annotation = f"{parent_schema.unit_name}. {unit.model}."

            await print_image(unit.barcode.filename, self.employee.rfid_card_id, annotation=annotation)  # type: ignore

        return unit

    def _validate_state_transition(self, new_state: State) -> None:
        """check if state transition can be performed using the map"""
        if new_state not in STATE_TRANSITION_MAP.get(self.state, []):
            raise StateForbiddenError(f"State transition from {self.state.name} to {new_state.name} is not allowed.")

    def switch_state(self, new_state: State) -> None:
        """apply new state to the workbench"""
        assert isinstance(new_state, State)
        self._validate_state_transition(new_state)
        logger.info(f"Workbench no.{self.number} state changed: {self.state.name} -> {new_state.name}")
        self.state = new_state

    def log_in(self, employee: Employee) -> None:
        """authorize employee"""
        self._validate_state_transition(AUTHORIZED_IDLING_STATE)

        self.employee = employee
        logger.info(f"Employee {employee.name} is logged in at the workbench no. {self.number}")

        self.switch_state(AUTHORIZED_IDLING_STATE)

    def log_out(self) -> None:
        """log out the employee"""
        self._validate_state_transition(AWAIT_LOGIN_STATE)

        if self.state is UNIT_ASSIGNED_IDLING_STATE:
            self.remove_unit()

        logger.info(f"Employee {self.employee.name} was logged out the Workbench {self.number}")  # type: ignore
        self.employee = None

        self.switch_state(AWAIT_LOGIN_STATE)

    def assign_unit(self, unit: Unit) -> None:
        """assign a unit to the workbench"""
        self._validate_state_transition(UNIT_ASSIGNED_IDLING_STATE)

        self.unit = unit
        logger.info(f"Unit {unit.internal_id} has been assigned to the workbench")

        if not unit.components_filled:
            logger.info(
                f"Unit {unit.internal_id} is a composition with unsatisfied component requirements. Entering component gathering state."
            )
            self.switch_state(GATHER_COMPONENTS_STATE)
        else:
            self.switch_state(UNIT_ASSIGNED_IDLING_STATE)

    def remove_unit(self) -> None:
        """remove a unit from the workbench"""
        self._validate_state_transition(AUTHORIZED_IDLING_STATE)

        logger.info(f"Unit {self.unit.internal_id} has been removed from the workbench")  # type: ignore
        self.unit = None

        self.switch_state(AUTHORIZED_IDLING_STATE)

    async def start_operation(self, production_stage_name: str, additional_info: AdditionalInfo) -> None:
        """begin work on the provided unit"""
        self._validate_state_transition(PRODUCTION_STAGE_ONGOING_STATE)

        self.unit.start_operation(self.employee, production_stage_name, additional_info)  # type: ignore

        if self.camera is not None and self.employee is not None:
            await self.camera.start(self.employee.rfid_card_id)

        logger.info(
            f"Started operation {production_stage_name} on the unit {self.unit.internal_id} at the workbench no. {self.number}"  # type: ignore
        )

        self.switch_state(PRODUCTION_STAGE_ONGOING_STATE)

    async def assign_component_to_unit(self, component: Unit) -> None:
        """assign provided component to a composite unit"""
        assert (
            self.state is GATHER_COMPONENTS_STATE and self.unit is not None
        ), f"Cannot assign components unless WB is in state {GATHER_COMPONENTS_STATE.name}"

        self.unit.assign_component(component)

        if self.unit.components_filled:
            for component in self.unit.components_units:
                await self._database.update_unit(component)

            self.switch_state(UNIT_ASSIGNED_IDLING_STATE)

    async def end_operation(self, additional_info: tp.Optional[AdditionalInfo] = None, premature: bool = False) -> None:
        """end work on the provided unit"""
        self._validate_state_transition(UNIT_ASSIGNED_IDLING_STATE)
        assert self.unit is not None, "Unit not assigned"

        logger.info("Trying to end operation")

        ipfs_hashes: tp.List[str] = []
        if self.camera is not None and self.employee is not None:
            await self.camera.end(self.employee.rfid_card_id)

            file: tp.Optional[str] = self.camera.record.remote_file_path  # type: ignore

            if file is not None:
                data = await publish_file(file_path=Path(file), rfid_card_id=self.employee.rfid_card_id)

                if data is not None:
                    cid, link = data
                    ipfs_hashes.append(cid)

        await self.unit.end_operation(ipfs_hashes, additional_info, premature)
        await self._database.update_unit(self.unit)

        self.switch_state(UNIT_ASSIGNED_IDLING_STATE)

    async def upload_unit_passport(self) -> None:
        """upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics"""
        assert self.unit is not None, "Unit not assigned"
        assert self.employee is not None, "Employee not logged in"

        passport_file_path = await self.unit.construct_unit_passport()

        if not config.feecc_io_gateway.autonomous_mode:
            res = await publish_file(file_path=Path(passport_file_path), rfid_card_id=self.employee.rfid_card_id)
            cid, link = res or ("", "")

            if config.printer.print_qr and (
                not config.printer.print_qr_only_for_composite
                or self.unit.schema.is_composite
                or not self.unit.schema.is_a_component
            ):
                short_url, qrcode_path = generate_qr_code(link)
                await print_image(
                    qrcode_path,
                    self.employee.rfid_card_id,
                    annotation=f"{self.unit.model} (ID: {self.unit.internal_id}). {short_url}",
                )

            if config.printer.print_security_tag:
                seal_tag_img: str = create_seal_tag()
                await print_image(seal_tag_img, self.employee.rfid_card_id)

            if config.robonomics_network.enable_datalog and res is not None:
                post_to_datalog(cid)

        if self.unit.is_in_db:
            await self._database.update_unit(self.unit)
        else:
            await self._database.upload_unit(self.unit)
