from __future__ import annotations

import logging
import typing as tp
from abc import ABC, abstractmethod
from copy import deepcopy

from . import (
    _Printer as Printer,
    _image_generation as image_generation,
    _short_url_generator as url_generator,
)
from .Types import Config

if tp.TYPE_CHECKING:
    from ._Agent import Agent
    from .Employee import Employee
    from .Unit import Unit
    from .database import DbWrapper


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


class ProductionStageStarting(State):
    """A state to run when a production stage is being started"""

    def run(
        self,
        unit: Unit,
        employee: Employee,
        production_stage_name: str,
        additional_info: tp.Dict[str, tp.Any],
    ) -> None:
        self._context.associated_unit = unit
        unit.employee = employee
        unit.start_session(production_stage_name, employee.passport_code, additional_info)

        if self._context.latest_video is not None and self._config["print_qr"]["enable"]:
            qrcode: str = self._generate_qr_code()
            self._print_qr_code(qrcode)

        if self._config["print_security_tag"]["enable"]:
            self._print_seal_tag()

        self._start_recording(unit)
        self._context.execute_state(ProductionStageOngoing, background=False)

    def _print_qr_code(self, pic_name: str) -> None:
        """print the QR code onto a sticker"""
        logging.debug("Printing QR code image")
        Printer.Task(pic_name, self._config)

    def _generate_qr_code(self) -> str:
        """generate a QR code with the short link"""
        if self._context.latest_video is None:
            raise FileNotFoundError("There is no video associated with the Agent")
        logging.debug("Generating short url (a dummy for now)")
        short_url: str = url_generator.generate_short_url(self._config)
        self._context.latest_video.short_url = short_url  # todo bug
        logging.debug("Generating QR code image file")
        qr_code_image: str = image_generation.create_qr(short_url, self._config)
        self._context.latest_video.qrcode = qr_code_image
        return qr_code_image

    def _print_seal_tag(self) -> None:
        """generate and print a seal tag"""
        logging.info("Printing seal tag")
        seal_tag_img: str = image_generation.create_seal_tag(self._config)
        Printer.Task(seal_tag_img, self._config)

    def _start_recording(self, unit: Unit) -> None:
        """start recording a video"""
        if self._context.associated_camera is None:
            logging.error("Cannot start recording: associated camera is None")
        else:
            self._context.associated_camera.start_record(unit.uuid)


class ProductionStageOngoing(State):
    """
    State when job is ongoing
    """

    def run(self) -> None:
        pass


class ProductionStageEnding(State):
    """
    State when production stage is being ended
    """

    def run(
        self, database: DbWrapper, additional_info: tp.Optional[tp.Dict[str, tp.Any]] = None
    ) -> None:
        # make a copy of unit to work with securely in another thread
        if self._context.associated_unit is None:
            raise ValueError("No context associated unit found")
        else:
            unit: Unit = deepcopy(self._context.associated_unit)
            self._context.associated_unit = None

        # stop recording and save the file
        if self._context.associated_camera is not None:
            self._context.latest_video = self._context.associated_camera.stop_record()

        # publish video into IPFS and pin to Pinata
        # update the short link to point to an actual recording
        ipfs_hashes: tp.List[str] = []
        file = self._context.latest_video
        if file is not None:
            self._context.io_gateway.send(file)

            if file.ipfs_hash is not None:
                ipfs_hashes.append(file.ipfs_hash)

        # add video IPFS hash to the passport
        unit.end_session(database, ipfs_hashes, additional_info)

        # reset own state
        self._context.execute_state(AuthorizedIdling, background=False)


class UnitWrapUp(State):
    """
    State when unit data are being wrapped up
    Uploaded to IPFS, pinned to Pinata, etc
    (optional if workbench isn't creating units)
    """

    def run(self) -> None:
        pass
