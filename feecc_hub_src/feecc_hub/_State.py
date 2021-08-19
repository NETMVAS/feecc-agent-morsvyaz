from __future__ import annotations

import typing as tp
from abc import ABC, abstractmethod
from copy import deepcopy

from loguru import logger

from .database import MongoDbWrapper
from .Types import AdditionalInfo, GlobalConfig
from .Config import Config
from ._external_io_operations import ExternalIoGateway
from .exceptions import CameraNotFoundError, StateForbiddenError, UnitNotFoundError

if tp.TYPE_CHECKING:
    from .Employee import Employee
    from .Unit import Unit
    from .WorkBench import WorkBench


class State(ABC):
    """abstract State class for states to inherit from"""

    def __init__(self, context: WorkBench) -> None:
        """:param context: object of type WorkBench which executes the provided state"""
        self._context: WorkBench = context

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def description(self) -> str:
        """returns own docstring which describes the state"""
        return self.__doc__ or ""

    @property
    def _config(self) -> GlobalConfig:
        return Config().global_config

    @abstractmethod
    @tp.no_type_check
    def perform_on_apply(self, *args, **kwargs) -> None:
        """state action executor (to be overridden)"""
        raise NotImplementedError

    @tp.no_type_check
    def start_shift(self, employee: Employee) -> None:
        """authorize employee"""
        self._context.employee = employee
        logger.info(f"Employee {employee.name} is logged in at the workbench no. {self._context.number}")
        database: MongoDbWrapper = MongoDbWrapper()
        self._context.apply_state(AuthorizedIdling, database)

    @tp.no_type_check
    def end_shift(self) -> None:
        """log out the employee"""
        logger.info(f"Employee '{self._context.employee}' was logged out the Workbench {self._context.number}")
        self._context.employee = None
        self._context.apply_state(AwaitLogin)

    @tp.no_type_check
    def start_operation(self, unit: Unit, production_stage_name: str, additional_info: AdditionalInfo) -> None:
        """begin work on the provided unit"""
        logger.info(
            f"Started operation {production_stage_name} on the unit {unit.internal_id} at the workbench no. {self._context.number}"
        )
        self._context.apply_state(
            ProductionStageOngoing,
            unit,
            self._context.employee,
            production_stage_name,
            additional_info,
        )

    @tp.no_type_check
    def end_operation(self, unit_internal_id: str, additional_info: tp.Optional[AdditionalInfo] = None) -> None:
        """end work on the provided unit"""
        # make sure requested unit is associated with this workbench
        if unit_internal_id == self._context.unit_in_operation:
            database: MongoDbWrapper = MongoDbWrapper()
            logger.info(f"Trying to end operation")
            self._context.apply_state(AuthorizedIdling, database)
        else:
            message = f"Unit with int_id {unit_internal_id} isn't associated with the Workbench {self._context.number}"
            logger.error(message)
            raise UnitNotFoundError(message)


class AwaitLogin(State, ABC):
    """State when the workbench is empty and waiting for an employee authorization"""

    def perform_on_apply(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        pass

    def end_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot log out: no one is logged in at the workbench {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)

    def start_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot start operation: no one is logged in at the workbench {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)

    def end_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot end operation: no one is logged in at the workbench {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)


class AuthorizedIdling(State):
    """State when an employee was authorized at the workbench but doing nothing"""

    def perform_on_apply(self, database: MongoDbWrapper, additional_info: tp.Optional[AdditionalInfo] = None) -> None:
        if self._context.previous_state == ProductionStageOngoing:
            logger.info(f"Ending operation {self._context}")
            self._end_operation(database, additional_info)

    def _end_operation(self, database: MongoDbWrapper, additional_info: tp.Optional[AdditionalInfo] = None) -> None:
        """end previous operation"""
        unit: Unit = self._get_unit_copy()
        ipfs_hashes: tp.List[str] = []
        if self._context.camera is not None:
            self._stop_recording()
            ipfs_hash: tp.Optional[str] = self._publish_record()
            if ipfs_hash:
                ipfs_hashes.append(ipfs_hash)
        unit.end_session(database, ipfs_hashes, additional_info)

    def _publish_record(self) -> tp.Optional[str]:
        """publish video into IPFS and pin to Pinata. Then update the short link
        to point to an actual recording"""
        file = self._context.camera.record if self._context.camera else None
        if file is not None:
            ExternalIoGateway().send(file)
            return file.ipfs_hash
        return None

    def _get_unit_copy(self) -> Unit:
        """make a copy of unit to work with securely in another thread"""
        if self._context.associated_unit is None:
            raise ValueError("No context associated unit found")
        unit: Unit = deepcopy(self._context.associated_unit)
        self._context.associated_unit = None
        return unit

    def _stop_recording(self) -> None:
        """stop recording and save the file"""
        if self._context.camera is None:
            raise CameraNotFoundError("No associated camera")
        if self._context.camera.record is not None:
            self._context.camera.stop_record()

    def start_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot log in: a worker is already logged in at the workbench no. {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)

    def end_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot end operation: there is no ongoing operation at the workbench no. {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)


class ProductionStageOngoing(State):
    """State when job is ongoing"""

    def perform_on_apply(
        self,
        unit: Unit,
        employee: Employee,
        production_stage_name: str,
        additional_info: AdditionalInfo,
    ) -> None:
        self._context.associated_unit = unit
        unit.employee = employee
        unit.start_session(production_stage_name, employee.passport_code, additional_info)
        if self._context.camera:
            self._start_recording(unit)

    def _start_recording(self, unit: Unit) -> None:
        """start recording a video"""
        if self._context.camera is None:
            logger.error("Cannot start recording: associated camera is None")
        else:
            self._context.camera.start_record(unit.uuid)
