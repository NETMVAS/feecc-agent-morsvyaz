from __future__ import annotations

import logging
import threading
import typing as tp

from .Unit import Unit
from ._Camera import Camera
from ._State import State
from ._external_io_operations import ExternalIoGateway, File

if tp.TYPE_CHECKING:
    from .WorkBench import WorkBench
    from .Types import Config


class Agent:
    """Handles agent's state management and high level operation"""

    def __init__(self, workbench: WorkBench) -> None:
        """agent has an instance of Passport and Camera associated with it"""
        self._workbench: WorkBench = workbench
        self._state: tp.Optional[State] = None
        self._state_thread_list: tp.List[threading.Thread] = []
        self.io_gateway: ExternalIoGateway = ExternalIoGateway(self.config)
        self.associated_unit: tp.Optional[Unit] = None
        self.associated_camera: tp.Optional[Camera] = self._workbench.camera
        self.latest_video: tp.Optional[File] = None

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
    def state_name(self) -> str:
        if self._state is None:
            return ""
        else:
            return self._state.name

    @property
    def state_description(self) -> str:
        if self._state is not None:
            return str(self._state.description)
        else:
            return ""

    @property
    def config(self) -> Config:
        return self._workbench.config

    def execute_state(
        self, state: tp.Type[State], background: bool = True, *args: tp.Any, **kwargs: tp.Any
    ) -> None:
        """execute provided state in the background"""
        self._state = state(self)
        if self._state is None:
            raise ValueError("Current state undefined")

        logging.info(f"Agent state is now {self._state.name}")

        if background:
            # execute state in the background
            logging.debug(f"Trying to execute state: {state}")
            self._state_thread = threading.Thread(target=self._state.run, args=args, kwargs=kwargs)
            self._state_thread.start()
        else:
            self._state.run(*args, **kwargs)
