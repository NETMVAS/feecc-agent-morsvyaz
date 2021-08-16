from __future__ import annotations

import typing as tp
from abc import ABC, abstractmethod
from copy import deepcopy

from loguru import logger

from . import (
    _Printer as Printer,
    _image_generation as image_generation,
    _short_url_generator as url_generator,
)
from .Types import AdditionalInfo, Config
from ._external_io_operations import ExternalIoGateway
from .exceptions import CameraNotFoundError, StateForbiddenError, UnitNotFoundError

if tp.TYPE_CHECKING:
    from .database import DbWrapper
    from .WorkBench import WorkBench
    from .Employee import Employee
    from .Unit import Unit


class State(ABC):
    """abstract State class for states to inherit from"""

    def __init__(
        self, context: WorkBench, io_gateway: tp.Optional[ExternalIoGateway] = None
    ) -> None:
        """:param context: object of type Agent which executes the provided state"""
        self._context: WorkBench = context
        self._io_gateway: ExternalIoGateway = io_gateway or ExternalIoGateway(self._config)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def description(self) -> str:
        """returns own docstring which describes the state"""
        return self.__doc__ or ""

    @property
    def _config(self) -> Config:
        return self._context.config

    @abstractmethod
    @tp.no_type_check
    def perform_on_apply(self, *args, **kwargs) -> None:
        """state action executor (to be overridden)"""
        raise NotImplementedError

    @tp.no_type_check
    def start_shift(self, employee: Employee) -> None:
        """authorize employee"""
        self._context.employee = employee
        logger.info(
            f"Employee {employee.rfid_card_id} is logged in at the workbench no. {self._context.number}"
        )
        database: DbWrapper = self._context.associated_hub.database
        self._context.apply_state(AuthorizedIdling, database)

    @tp.no_type_check
    def end_shift(self) -> None:
        """log out the employee"""
        self._context.employee = None
        self._context.apply_state(AwaitLogin)

    @tp.no_type_check
    def start_operation(
        self, unit: Unit, production_stage_name: str, additional_info: AdditionalInfo
    ) -> None:
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
    def end_operation(
        self, unit_internal_id: str, additional_info: tp.Optional[AdditionalInfo] = None
    ) -> None:
        """end work on the provided unit"""
        # make sure requested unit is associated with this workbench
        if unit_internal_id == self._context.unit_in_operation:
            database: DbWrapper = self._context.associated_hub.database
            self._context.apply_state(AuthorizedIdling, database)
        else:
            message = f"Unit with int. id {unit_internal_id} isn't associated with the Workbench {self._context.number}"
            logger.error(message)
            raise UnitNotFoundError(message)


class AwaitLogin(State, ABC):
    """State when the workbench is empty and waiting for an employee authorization"""

    def perform_on_apply(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        pass

    def end_shift(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot log out: no one is logged in at the workbench no. {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)

    def start_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = f"Cannot start operation: no one is logged in at the workbench no. {self._context.number}"
        logger.error(msg)
        raise StateForbiddenError(msg)

    def end_operation(self, *args: tp.Any, **kwargs: tp.Any) -> None:
        msg = (
            f"Cannot end operation: no one is logged in at the workbench no. {self._context.number}"
        )
        logger.error(msg)
        raise StateForbiddenError(msg)


class AuthorizedIdling(State):
    """State when an employee was authorized at the workbench but doing nothing"""

    def perform_on_apply(
        self, database: DbWrapper, additional_info: tp.Optional[AdditionalInfo] = None
    ) -> None:
        if self._context.previous_state == ProductionStageOngoing:
            logger.info("Ending operation")
            self._end_operation(database, additional_info)

    def _end_operation(
        self, database: DbWrapper, additional_info: tp.Optional[AdditionalInfo] = None
    ) -> None:
        """end previous operation"""
        unit: Unit = self._get_unit_copy()
        ipfs_hashes: tp.List[str] = []
        if self._context.camera is not None:
            self._stop_recording()
            ipfs_hashes = self._publish_record()
        unit.end_session(database, ipfs_hashes, additional_info)

    def _publish_record(self) -> tp.List[str]:
        """publish video into IPFS and pin to Pinata. Then update the short link
        to point to an actual recording"""
        ipfs_hashes: tp.List[str] = []
        if self._context.camera is None:
            raise CameraNotFoundError("No associated camera")
        if self._context.camera.record is None:
            raise CameraNotFoundError("No record found")
        file = self._context.camera.record
        if file is not None:
            self._io_gateway.send(file)
            if file.ipfs_hash is not None:
                ipfs_hashes.append(file.ipfs_hash)
        return ipfs_hashes

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
        if (
            self._context.camera
            and self._context.camera.record
            and self._config["print_qr"]["enable"]
        ):
            qrcode: str = self._generate_qr_code()
            self._print_qr_code(qrcode)
            self._start_recording(unit)
        if self._config["print_security_tag"]["enable"]:
            self._print_seal_tag()

    def _print_qr_code(self, pic_name: str) -> None:
        """print the QR code onto a sticker"""
        logger.debug("Printing QR code image")
        Printer.PrinterTask(pic_name, self._config)

    def _generate_qr_code(self) -> str:
        """generate a QR code with the short link"""
        if not (self._context.camera and self._context.camera.record):
            return ""
        logger.debug("Generating short url (a dummy for now)")
        short_url: str = url_generator.generate_short_url(self._config)
        self._context.camera.record.short_url = short_url
        logger.debug("Generating QR code image file")
        qr_code_image: str = image_generation.create_qr(short_url, self._config)
        self._context.camera.record.qrcode = qr_code_image
        return qr_code_image

    def _print_seal_tag(self) -> None:
        """generate and print a seal tag"""
        logger.info("Printing seal tag")
        seal_tag_img: str = image_generation.create_seal_tag(self._config)
        Printer.PrinterTask(seal_tag_img, self._config)

    def _start_recording(self, unit: Unit) -> None:
        """start recording a video"""
        if self._context.camera is None:
            logger.error("Cannot start recording: associated camera is None")
        else:
            self._context.camera.start_record(unit.uuid)
