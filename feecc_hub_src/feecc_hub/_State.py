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
    """
    State when production stage being started
    """

    def run(
        self,
        unit: Unit,
        employee: Employee,
        production_stage_name: str,
        additional_info: tp.Dict[str, tp.Any],
    ) -> None:
        # assign unit
        self._context.associated_unit = unit

        # assign employee to unit
        self._context.associated_unit.employee = employee

        # start operation at the unit
        self._context.associated_unit.start_session(
            production_stage_name, employee.passport_code, additional_info
        )

        # start the recording in the background and send the path to the video
        try:
            unit = self._context.associated_unit

            if unit is None:
                raise ValueError("No associated unit found")

            passport_id = unit.uuid

        except AttributeError as E:
            logging.error(
                f"Failed to start video recording: error retrieving associated passport ID.\n\
                        self._context.associated_passport = {self._context.associated_unit} {E}"
            )
            return

        if self._context.latest_video is not None and self._context.config["print_qr"]["enable"]:
            # generate a video short link (a dummy for now)
            self._context.latest_video.short_url = url_generator.generate_short_url(
                self._context.config
            )[1]

            # generate a QR code with the short link
            if self._context.latest_video.short_url is not None:
                self._context.latest_video.qrcode = image_generation.create_qr(
                    link=self._context.latest_video.short_url, config=self._context.config
                )

                # print the QR code onto a sticker if set to do so in the config
                if self._context.config["print_qr"]["enable"]:
                    Printer.Task(
                        picname=self._context.latest_video.qrcode, config=self._context.config
                    )

        # print the seal tag onto a sticker if set to do so in the config
        if self._context.config["print_security_tag"]["enable"]:
            seal_file_path = image_generation.create_seal_tag(self._context.config)
            Printer.Task(picname=seal_file_path, config=self._context.config)

        # start recording a video
        if self._context.associated_camera is not None:
            logging.debug("Reached target 1")
            self._context.associated_camera.start_record(passport_id)
            logging.debug("Reached target 6")
        else:
            logging.error("Cannot start recording: associated camera is None")

        self._context.execute_state(ProductionStageOngoing, background=False)


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
