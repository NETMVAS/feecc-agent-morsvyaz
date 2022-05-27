import asyncio
import os
from pathlib import Path

from loguru import logger

from ._image_generation import create_qr, create_seal_tag
from ._short_url_generator import generate_short_url
from .Camera import Camera
from .config import CONFIG
from .database import MongoDbWrapper
from .Employee import Employee
from .exceptions import StateForbiddenError
from .ipfs import publish_file
from .models import ProductionSchema
from .passport_generator import construct_unit_passport
from .printer import print_image
from .robonomics import post_to_datalog
from .Singleton import SingletonMeta
from .states import STATE_TRANSITION_MAP, State
from .Types import AdditionalInfo
from .Unit import Unit
from .unit_utils import UnitStatus
from .utils import timestamp

STATE_SWITCH_EVENT = asyncio.Event()


class WorkBench(metaclass=SingletonMeta):
    """
    Work bench is a union of an Employee, working at it and Camera attached.
    It provides highly abstract interface for interaction with them
    """

    @logger.catch
    def __init__(self) -> None:
        self._database: MongoDbWrapper = MongoDbWrapper()
        self.number: int = CONFIG.workbench.number
        camera_number: int | None = CONFIG.camera.camera_no
        self.camera: Camera | None = Camera(camera_number) if camera_number and CONFIG.camera.enable else None
        self.employee: Employee | None = None
        self.unit: Unit | None = None
        self.state: State = State.AWAIT_LOGIN_STATE

        logger.info(f"Workbench {self.number} was initialized")

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    async def create_new_unit(self, schema: ProductionSchema) -> Unit:
        """initialize a new instance of the Unit class"""
        if self.state != State.AUTHORIZED_IDLING_STATE:
            raise StateForbiddenError("Cannot create a new unit unless workbench has state AuthorizedIdling")

        unit = Unit(schema)
        await self._database.push_unit(unit)

        if CONFIG.printer.print_barcode and CONFIG.printer.enable:
            if unit.schema.parent_schema_id is None:
                annotation = unit.schema.unit_name
            else:
                parent_schema = await self._database.get_schema_by_id(unit.schema.parent_schema_id)
                annotation = f"{parent_schema.unit_name}. {unit.model_name}."

            await print_image(unit.barcode.filename, self.employee.rfid_card_id, annotation=annotation)  # type: ignore
            os.remove(unit.barcode.filename)

        return unit

    def _validate_state_transition(self, new_state: State) -> None:
        """check if state transition can be performed using the map"""
        if new_state not in STATE_TRANSITION_MAP.get(self.state, []):
            raise StateForbiddenError(f"State transition from {self.state.value} to {new_state.value} is not allowed.")

    def switch_state(self, new_state: State) -> None:
        """apply new state to the workbench"""
        assert isinstance(new_state, State)
        self._validate_state_transition(new_state)
        logger.info(f"Workbench no.{self.number} state changed: {self.state.value} -> {new_state.value}")
        self.state = new_state
        STATE_SWITCH_EVENT.set()

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    def log_in(self, employee: Employee) -> None:
        """authorize employee"""
        self._validate_state_transition(State.AUTHORIZED_IDLING_STATE)

        self.employee = employee
        logger.info(f"Employee {employee.name} is logged in at the workbench no. {self.number}")

        self.switch_state(State.AUTHORIZED_IDLING_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    def log_out(self) -> None:
        """log out the employee"""
        self._validate_state_transition(State.AWAIT_LOGIN_STATE)

        if self.state == State.UNIT_ASSIGNED_IDLING_STATE:
            self.remove_unit()

        logger.info(f"Employee {self.employee.name} was logged out the Workbench {self.number}")  # type: ignore
        self.employee = None

        self.switch_state(State.AWAIT_LOGIN_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    def assign_unit(self, unit: Unit) -> None:
        """assign a unit to the workbench"""
        self._validate_state_transition(State.UNIT_ASSIGNED_IDLING_STATE)

        allowed = (UnitStatus.production, UnitStatus.revision)
        assert unit.status in allowed, f"Can only assign unit with status: {allowed}. {unit.status=}. Forbidden."

        self.unit = unit
        logger.info(f"Unit {unit.internal_id} has been assigned to the workbench")

        if not unit.components_filled:
            logger.info(
                f"Unit {unit.internal_id} is a composition with unsatisfied component requirements. Entering component gathering state."
            )
            self.switch_state(State.GATHER_COMPONENTS_STATE)
        else:
            self.switch_state(State.UNIT_ASSIGNED_IDLING_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    def remove_unit(self) -> None:
        """remove a unit from the workbench"""
        self._validate_state_transition(State.AUTHORIZED_IDLING_STATE)
        assert self.unit is not None, "Cannot remove unit. No unit is currently assigned to the workbench."

        logger.info(f"Unit {self.unit.internal_id} has been removed from the workbench")
        self.unit = None

        self.switch_state(State.AUTHORIZED_IDLING_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    async def start_operation(self, additional_info: AdditionalInfo) -> None:
        """begin work on the provided unit"""
        self._validate_state_transition(State.PRODUCTION_STAGE_ONGOING_STATE)
        assert self.unit is not None, "No unit is assigned to the workbench"
        assert self.employee is not None, "No employee is assigned to the workbench"

        self.unit.start_operation(self.employee, additional_info)

        if self.camera is not None and self.employee is not None:
            await self.camera.start(self.employee.rfid_card_id)

        self.switch_state(State.PRODUCTION_STAGE_ONGOING_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    async def assign_component_to_unit(self, component: Unit) -> None:
        """assign provided component to a composite unit"""
        assert (
            self.state == State.GATHER_COMPONENTS_STATE and self.unit is not None
        ), f"Cannot assign components unless WB is in state {State.GATHER_COMPONENTS_STATE}"

        self.unit.assign_component(component)

        if self.unit.components_filled:
            await self._database.push_unit(self.unit)
            self.switch_state(State.UNIT_ASSIGNED_IDLING_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    async def end_operation(self, additional_info: AdditionalInfo | None = None, premature: bool = False) -> None:
        """end work on the provided unit"""
        self._validate_state_transition(State.UNIT_ASSIGNED_IDLING_STATE)
        assert self.unit is not None, "No unit is assigned to the workbench"

        logger.info("Trying to end operation")
        override_timestamp = timestamp()

        ipfs_hashes: list[str] = []
        if self.camera is not None and self.employee is not None:
            await self.camera.end(self.employee.rfid_card_id)
            override_timestamp = timestamp()

            file: str | None = self.camera.record.remote_file_path  # type: ignore

            if file is not None:
                data = await publish_file(file_path=Path(file), rfid_card_id=self.employee.rfid_card_id)

                if data is not None:
                    cid, link = data
                    ipfs_hashes.append(cid)

        await self.unit.end_operation(
            video_hashes=ipfs_hashes,
            additional_info=additional_info,
            premature=premature,
            override_timestamp=override_timestamp,
        )
        await self._database.push_unit(self.unit)

        self.switch_state(State.UNIT_ASSIGNED_IDLING_STATE)

    @logger.catch(reraise=True, exclude=StateForbiddenError)
    async def upload_unit_passport(self) -> None:
        """upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics"""
        assert self.unit is not None, "No unit is assigned to the workbench"
        assert self.employee is not None, "No employee is assigned to the workbench"

        passport_file_path = await construct_unit_passport(self.unit)

        if CONFIG.ipfs_gateway.enable:
            res = await publish_file(file_path=Path(passport_file_path), rfid_card_id=self.employee.rfid_card_id)
            cid, link = res or ("", "")
            self.unit.passport_ipfs_cid = cid

            print_qr = CONFIG.printer.print_qr and (
                not CONFIG.printer.print_qr_only_for_composite
                or self.unit.schema.is_composite
                or not self.unit.schema.is_a_component
            )

            if print_qr:
                short_url: str = await generate_short_url(link)
                self.unit.passport_short_url = short_url
                qrcode_path = create_qr(short_url)
                await print_image(
                    qrcode_path,
                    self.employee.rfid_card_id,
                    annotation=f"{self.unit.model_name} (ID: {self.unit.internal_id}). {short_url}",
                )
                os.remove(qrcode_path)
            else:

                async def _bg_generate_short_url(url: str, unit_internal_id: str) -> None:
                    short_link = await generate_short_url(url)
                    await MongoDbWrapper().unit_update_single_field(unit_internal_id, "passport_short_url", short_link)

                asyncio.create_task(_bg_generate_short_url(link, self.unit.internal_id))

            if CONFIG.printer.print_security_tag:
                seal_tag_img: str = create_seal_tag()
                await print_image(seal_tag_img, self.employee.rfid_card_id)
                os.remove(seal_tag_img)

            if CONFIG.robonomics.enable_datalog and res is not None:
                asyncio.create_task(post_to_datalog(cid, self.unit.internal_id))

        await self._database.push_unit(self.unit)

    async def shutdown(self) -> None:
        logger.info("Workbench shutdown sequence initiated")

        if self.state == State.PRODUCTION_STAGE_ONGOING_STATE:
            logger.warning(
                "Ending ongoing operation prematurely. Reason: Unfinished when Workbench shutdown sequence initiated"
            )
            await self.end_operation(
                premature=True,
                additional_info={"Ended reason": "Unfinished when Workbench shutdown sequence initiated"},
            )

        if self.state in (State.UNIT_ASSIGNED_IDLING_STATE, State.GATHER_COMPONENTS_STATE):
            self.remove_unit()

        if self.state == State.AUTHORIZED_IDLING_STATE:
            self.log_out()

        logger.info("Workbench shutdown sequence complete")
