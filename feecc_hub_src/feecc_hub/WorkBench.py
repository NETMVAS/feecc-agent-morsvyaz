from __future__ import annotations

import typing as tp

from loguru import logger
from .IO_gateway import publish_file
from .Camera import Camera
from .Employee import Employee
from .Singleton import SingletonMeta
from .Types import AdditionalInfo
from .Unit import Unit
from .states import (
    AUTHORIZED_IDLING_STATE,
    AWAIT_LOGIN_STATE,
    PRODUCTION_STAGE_ONGOING_STATE,
    STATE_TRANSITION_MAP,
    State,
    UNIT_ASSIGNED_IDLING_STATE,
)
from .config import config
from .database import MongoDbWrapper
from .exceptions import StateForbiddenError


class WorkBench(metaclass=SingletonMeta):
    """
    Work bench is a union of an Employee, working at it and Camera attached.
    It provides highly abstract interface for interaction with them
    """

    @logger.catch
    def __init__(self) -> None:
        self._database: MongoDbWrapper = MongoDbWrapper()

        self.number: int = config.workbench_config.number
        camera_number: tp.Optional[int] = config.workbench_config.hardware["camera"]
        self.camera: tp.Optional[Camera] = Camera(camera_number) if camera_number else None
        self.ip: str = config.workbench_config.api_socket.split(":")[0]
        self.employee: tp.Optional[Employee] = None
        self.unit: tp.Optional[Unit] = None
        self.state: State = AWAIT_LOGIN_STATE

        logger.info(f"Workbench {self.number} was initialized")

    async def create_new_unit(self, unit_type: str) -> Unit:
        """initialize a new instance of the Unit class"""
        unit = Unit(unit_type)
        await self._database.upload_unit(unit)

        if unit.internal_id is None:
            raise ValueError("Unit internal_id is None")

        return unit

    def _validate_state_transition(self, new_state: State) -> None:
        """check if state transition can be performed using the map"""
        if new_state not in STATE_TRANSITION_MAP.get(self.state, []):
            raise StateForbiddenError(f"State transition from {self.state.name} to {new_state.name} is not allowed.")

    def log_in(self, employee: Employee) -> None:
        """authorize employee"""
        self._validate_state_transition(AUTHORIZED_IDLING_STATE)

        self.employee = employee
        logger.info(f"Employee {employee.name} is logged in at the workbench no. {self.number}")

        self.state = AUTHORIZED_IDLING_STATE

    def log_out(self) -> None:
        """log out the employee"""
        self._validate_state_transition(AWAIT_LOGIN_STATE)

        if self.state is UNIT_ASSIGNED_IDLING_STATE:
            self.remove_unit()

        logger.info(f"Employee {self.employee.name} was logged out the Workbench {self.number}")  # type: ignore
        self.employee = None

        self.state = AWAIT_LOGIN_STATE

    def assign_unit(self, unit: Unit) -> None:
        """assign a unit to the workbench"""
        self._validate_state_transition(UNIT_ASSIGNED_IDLING_STATE)

        self.unit = unit
        logger.info(f"Unit {unit.internal_id} has been assigned to the workbench")

        self.state = UNIT_ASSIGNED_IDLING_STATE

    def remove_unit(self) -> None:
        """remove a unit from the workbench"""
        self._validate_state_transition(AUTHORIZED_IDLING_STATE)

        logger.info(f"Unit {self.unit.internal_id} has been removed from the workbench")  # type: ignore
        self.unit = None

        self.state = AUTHORIZED_IDLING_STATE

    async def start_operation(self, production_stage_name: str, additional_info: AdditionalInfo) -> None:
        """begin work on the provided unit"""
        self._validate_state_transition(PRODUCTION_STAGE_ONGOING_STATE)

        self.unit.start_session(self.employee, production_stage_name, additional_info)  # type: ignore

        if self.camera is not None:
            await self.camera.start()

        logger.info(
            f"Started operation {production_stage_name} on the unit {self.unit.internal_id} at the workbench no. {self.number}"  # type: ignore
        )

        self.state = PRODUCTION_STAGE_ONGOING_STATE

    async def end_operation(self, additional_info: tp.Optional[AdditionalInfo] = None) -> None:
        """end work on the provided unit"""
        self._validate_state_transition(UNIT_ASSIGNED_IDLING_STATE)

        logger.info("Trying to end operation")

        ipfs_hashes: tp.List[str] = []
        if self.camera is not None:
            await self.camera.end()

            file: tp.Optional[str] = self.camera.record.remote_file_path  # type: ignore

            if file is not None:
                data = await publish_file(file, self.employee.rfid_card_id)  # type: ignore

                if data is not None:
                    cid, link = data
                    ipfs_hashes.append(cid)

        self.unit.end_session(MongoDbWrapper(), ipfs_hashes, additional_info)  # type: ignore

        self.state = AUTHORIZED_IDLING_STATE
