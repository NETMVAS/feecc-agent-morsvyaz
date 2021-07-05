from __future__ import annotations

import logging
import threading
import typing as tp

from . import _external_io_operations as external_io
from .Unit import Unit
from ._Camera import Camera

if tp.TYPE_CHECKING:
    from .WorkBench import WorkBench
    from ._Types import Config, State


class Agent:
    """Handles agent's state management and high level operation"""

    def __init__(self, workbench: WorkBench) -> None:
        """agent is initialized with state 0 and has an instance of Passport and Camera associated with it"""
        self._workbench: WorkBench = workbench
        self._state: tp.Optional[State] = None
        self._state_thread_list: tp.List[threading.Thread] = []
        self.io_gateway: external_io.ExternalIoGateway = external_io.ExternalIoGateway(self.config)
        self.associated_unit: tp.Optional[Unit] = None

        camera = self._workbench.camera

        if camera is None:
            raise ValueError

        self.associated_camera: Camera = camera
        self.latest_record_filename: str = ""
        self.latest_record_short_link: str = ""
        self.latest_record_qrpic_filename: str = ""

    @property
    def _state_thread(self) -> tp.Optional[threading.Thread]:
        if self._state_thread_list:
            return self._state_thread_list[-1]
        else:
            return None

    @_state_thread.setter
    def _state_thread(self, state_thread: threading.Thread) -> None:
        self._state_thread_list.append(state_thread)

    @property
    def state_no(self) -> int:
        if self._state is None:
            return -1
        else:
            return int(self._state.number)

    @property
    def state_description(self) -> str:
        if self._state is not None:
            return str(self._state.state_description)
        else:
            return ""

    @property
    def config(self) -> Config:
        return self._workbench.config

    def execute_state(self, state: State, background: bool = True) -> None:
        """execute provided state in the background"""
        self._state = state(self)
        if self._state is None:
            raise ValueError

        logging.info(f"Agent state is now {self._state.name}")

        if background:
            # execute state in the background
            logging.debug(f"Trying to execute state: {state}")
            self._state_thread = threading.Thread(target=self._state.run)
            self._state_thread.start()
        else:
            self._state.run()
