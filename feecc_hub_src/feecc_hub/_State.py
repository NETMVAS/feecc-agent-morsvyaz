from __future__ import annotations

import typing as tp
from abc import ABC, abstractmethod
from copy import deepcopy

from loguru import logger

from . import _image_generation as image_generation
from . import _Printer as Printer
from . import _short_url_generator as url_generator
from .Types import AdditionalInfo, Config

if tp.TYPE_CHECKING:
    from ._Agent import Agent
    from .database import DbWrapper
    from .Employee import Employee
    from .Unit import Unit, ProductionStage


class State(ABC):
    """abstract State class for states to inherit from"""

    def __init__(self, context: Agent) -> None:
        """:param context: object of type Agent which executes the provided state"""
        self._context: Agent = context

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def description(self) -> tp.Optional[str]:
        """returns own docstring which describes the state"""
        return self.__doc__

    @property
    def _config(self) -> Config:
        return self._context.config

    @abstractmethod
    @tp.no_type_check
    def run(self, *args, **kwargs) -> None:
        """state action executor (to be overridden)"""
        raise NotImplementedError


class StateWithRecordHandling(State, ABC):
    """Abstract State implements recording methods (stop, start, publish)"""

    def _start_recording(self, unit: Unit) -> None:
        """start recording a video"""
        if self._context.associated_camera is None:
            logger.error("Cannot start recording: associated camera is None")
        else:
            self._context.associated_camera.start_record(unit.uuid)

    def _stop_recording(self) -> None:
        """stop recording and save the file"""
        if self._context.associated_camera is not None:
            self._context.latest_video = self._context.associated_camera.stop_record()

    def _publish_record(self) -> tp.List[str]:
        """publish video into IPFS and pin to Pinata. Then update the short link
        to point to an actual recording"""
        ipfs_hashes: tp.List[str] = []
        file = self._context.latest_video
        if file is not None:
            self._context.io_gateway.send(file)
            if file.ipfs_hash is not None:
                ipfs_hashes.append(file.ipfs_hash)
        return ipfs_hashes


class AwaitLogin(State):
    """
    State when the workbench is empty and waiting for an employee authorization
    """

    def run(self) -> None:
        pass


class AuthorizedIdling(State):
    """
    State when an employee was authorized at the workbench but doing nothing
    """

    def run(self) -> None:
        pass


class UnitDataGathering(State):
    """
    State when data is being gathered for creating new unit
    (optional if workbench isn't creating units)
    """

    def run(self) -> None:
        pass


class UnitInitialization(State):
    """
    State when new unit being created
    (optional if workbench isn't creating units)
    """

    def run(self) -> None:
        pass


class ProductionStageStarting(StateWithRecordHandling):
    """A state to run when a production stage is being started"""

    def run(
        self,
        unit: Unit,
        employee: Employee,
        production_stage_name: str,
        additional_info: AdditionalInfo,
    ) -> None:
        self._context.associated_unit = unit
        self._context.associated_unit.employee = employee
        self._start_session(production_stage_name, employee.passport_code, additional_info)

        if self._context.latest_video is not None and self._config["print_qr"]["enable"]:
            qrcode: str = self._generate_qr_code()
            self._print_qr_code(qrcode)

        if self._config["print_security_tag"]["enable"]:
            self._print_seal_tag()

        self._start_recording(unit)
        self._context.execute_state(ProductionStageOngoing, background=False)

    def _start_session(
        self,
        production_stage_name: str,
        employee_code_name: str,
        additional_info: tp.Optional[AdditionalInfo] = None,
    ) -> None:
        """begin the provided operation and save data about it"""

        if self._context.associated_unit is None:
            logger.error("No associated unit found")
            return None

        logger.info(
            f"Starting production stage {production_stage_name} for unit with int. id "
            f"{self._context.associated_unit.internal_id}, additional info {additional_info}"
        )

        operation = ProductionStage(
            name=production_stage_name,
            employee_name=employee_code_name,
            parent_unit_uuid=self._context.associated_unit.uuid,
            session_start_time=ProductionStage.timestamp(),
            additional_info=additional_info,
        )

        logger.debug(str(operation))
        self._context.associated_unit.current_operation = operation

    def _print_qr_code(self, pic_name: str) -> None:
        """print the QR code onto a sticker"""
        logger.debug("Printing QR code image")
        Printer.PrinterTask(pic_name, self._config)

    def _generate_qr_code(self) -> str:
        """generate a QR code with the short link"""
        if self._context.latest_video is None:
            raise FileNotFoundError("There is no video associated with the Agent")
        logger.debug("Generating short url (a dummy for now)")
        short_url: str = url_generator.generate_short_url(self._config)
        logger.debug(
            f"Target 1: {self._context.latest_video.short_url}, file: {repr(self._context.latest_video)}"
        )
        self._context.latest_video.short_url = short_url  # todo bug
        logger.debug(
            f"Target 2: {self._context.latest_video.short_url}, file: {repr(self._context.latest_video)}"
        )
        logger.debug("Generating QR code image file")
        qr_code_image: str = image_generation.create_qr(short_url, self._config)
        self._context.latest_video.qrcode = qr_code_image
        return qr_code_image

    def _print_seal_tag(self) -> None:
        """generate and print a seal tag"""
        logger.info("Printing seal tag")
        seal_tag_img: str = image_generation.create_seal_tag(self._config)
        Printer.PrinterTask(seal_tag_img, self._config)


class ProductionStageOngoing(State):
    """
    State when job is ongoing
    """

    def run(self) -> None:
        pass


class ProductionStageEnding(StateWithRecordHandling):
    """A state to run when a production stage is being ended"""

    def run(self, database: DbWrapper, additional_info: tp.Optional[AdditionalInfo] = None) -> None:
        # unit: Unit = self._get_unit_copy()
        self._stop_recording()
        ipfs_hashes: tp.List[str] = self._publish_record()
        self._end_session(database, ipfs_hashes, additional_info)
        self._context.execute_state(AuthorizedIdling, background=False)

    def _end_session(
        self,
        database: DbWrapper,
        video_hashes: tp.Optional[tp.List[str]] = None,
        additional_info: tp.Optional[AdditionalInfo] = None,
    ) -> None:
        """
        wrap up the session when video recording stops and save video data
        as well as session end timestamp
        """
        if self._context.associated_unit is None:
            logger.error("No associated unit found")
            return None

        if self._context.associated_unit.current_operation is None:
            raise ValueError("No ongoing operations found")

        logger.info(
            f"Ending production stage {self._context.associated_unit.current_operation.name}"
        )
        operation = deepcopy(self._context.associated_unit.current_operation)
        operation.session_end_time = ProductionStage.timestamp()

        if video_hashes:
            operation.video_hashes = video_hashes

        if additional_info:
            if operation.additional_info is not None:
                operation.additional_info = {
                    **operation.additional_info,
                    **additional_info,
                }
            else:
                operation.additional_info = additional_info

        self._context.associated_unit.unit_biography[-1] = operation
        logger.debug(
            f"Unit biography stage count is now {len(self._context.associated_unit.unit_biography)}"
        )
        self._context.associated_unit.employee = None
        database.update_unit(self._context.associated_unit)

    def _get_unit_copy(self) -> Unit:
        """make a copy of unit to work with securely in another thread"""
        if self._context.associated_unit is None:
            raise ValueError("No context associated unit found")
        unit: Unit = deepcopy(self._context.associated_unit)
        self._context.associated_unit = None
        return unit


class UnitWrapUp(State):
    """
    State when unit data are being wrapped up
    Uploaded to IPFS, pinned to Pinata, etc
    (optional if workbench isn't creating units)
    """

    def run(self) -> None:
        pass
