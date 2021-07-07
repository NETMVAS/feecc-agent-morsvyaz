from __future__ import annotations

import logging
import re
import typing as tp
from abc import ABC, abstractmethod

from . import _Printer as Printer
from . import _image_generation as image_generation
from . import _short_url_generator as url_generator

if tp.TYPE_CHECKING:
    from ._Agent import Agent


class State(ABC):
    """abstract State class for states to inherit from"""

    def __init__(self, context: Agent) -> None:
        """:param context: object of type Agent which executes the provided state"""
        self.state_description: str = "Abstract State Object"
        self._context: Agent = context

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def number(self) -> int:
        """extract own state number from the class name"""
        try:
            state_no = re.findall("\d+", self.name)[0]
            return int(state_no)
        except IndexError:
            logging.error(f"Name of the state '{self.name}' contains no digits. Rename the class.")
            return -1

    @abstractmethod
    @tp.no_type_check
    def run(self, *args, **kwargs) -> None:
        """state action executor (to be overridden)"""
        raise NotImplementedError


class State0(State):
    """at state 0 agent awaits for an incoming RFID event and is practically sleeping"""

    def __init__(self, context: Agent) -> None:
        super().__init__(context)
        self.state_description: str = (
            "At state 0 agent awaits for an incoming RFID event and is practically sleeping"
        )

    def run(self) -> None:
        pass


class State1(State):
    """
    at state 1 agent awaits for an incoming RFID event OR form post, thus operation is
    primarily done in app.py handlers, sleeping
    """

    def __init__(self, context: Agent) -> None:
        super().__init__(context)
        self.state_description: str = """
            at state 1 agent awaits for an incoming RFID event OR form post, thus operation is
            primarily done in app.py handlers, sleeping
            """

    def run(self) -> None:
        pass


class State2(State):
    """
    at state 2 agent is recording the work process using an IP camera and awaits an
    RFID event which would stop the recording
    """

    def __init__(self, context: Agent) -> None:
        super().__init__(context)
        self.state_description: str = """
            at state 2 agent is recording the work process using an IP camera and awaits an
            RFID event which would stop the recording
            """

    def run(self) -> None:
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

        # generate a video short link (a dummy for now)
        self._context.latest_record_short_link = url_generator.generate_short_url(
            self._context.config
        )[1]

        # generate a QR code with the short link
        self._context.latest_record_qrpic_filename = image_generation.create_qr(
            link=self._context.latest_record_short_link, config=self._context.config
        )

        # print the QR code onto a sticker if set to do so in the config
        if self._context.config["print_qr"]["enable"]:
            Printer.Task(
                picname=self._context.latest_record_qrpic_filename, config=self._context.config
            )

        # print the seal tag onto a sticker if set to do so in the config
        if self._context.config["print_security_tag"]["enable"]:
            seal_file_path = image_generation.create_seal_tag(self._context.config)

            Printer.Task(picname=seal_file_path, config=self._context.config)

        # start recording a video
        if self._context.associated_camera is not None:
            self._context.associated_camera.start_record(passport_id)


class State3(State):
    """
    then the agent receives an RFID event, recording is stopped and published to IPFS.
    Passport is dumped and also published into IPFS, it's checksum is stored in Robonomics.
    A short link is generated for the video and gets encoded in a QR code, which is printed on a sticker.
    When everything is done, background pinning of the files is started, own state is changed to 0.
    """

    def __init__(self, context: Agent) -> None:
        super().__init__(context)
        self.state_description: str = (
            "at state 3 Unit is wrapped up, it's passport is published online"
        )

    def run(self, additional_info: tp.Optional[tp.Dict[str, tp.Any]] = None) -> None:
        # stop recording and save the file
        if self._context.associated_camera is not None:
            self._context.latest_record_filename = self._context.associated_camera.stop_record()

        # publish video into IPFS and pin to Pinata
        # update the short link to point to an actual recording
        ipfs_hash = self._context.io_gateway.send(
            filename=self._context.latest_record_filename,
            keyword=self._context.latest_record_short_link.split("/")[-1],
        )

        if self._context.associated_unit is None:
            raise ValueError("No context associated unit found")

        ipfs_hashes: tp.List[str] = [ipfs_hash] if ipfs_hash is not None else []

        # add video IPFS hash to the passport
        self._context.associated_unit.end_session(ipfs_hashes, additional_info)
        self._context.associated_unit = None

        # change own state back to 0
        self._context.execute_state(State0, background=False)
