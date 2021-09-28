from __future__ import annotations

import threading
import typing as tp
from random import randint

from loguru import logger

from ._Camera import Camera
from ._State import AwaitLogin, State
from .Employee import Employee
from .Types import ConfigSection, WorkbenchConfig
from .Unit import Unit


class WorkBench:
    """
    Work bench is a union of an Employee, working at it and Camera attached.
    It provides highly abstract interface for interaction with them
    """

    def __init__(self, workbench_config: WorkbenchConfig) -> None:
        self._workbench_config: tp.Dict[str, tp.Any] = workbench_config
        self.number: int = self._workbench_config["workbench number"]
        self._associated_camera: tp.Optional[Camera] = self._get_camera()
        self.employee: tp.Optional[Employee] = None
        self.associated_unit: tp.Optional[Unit] = None
        logger.info(f"Workbench {self.number} was initialized")
        self.state: State = AwaitLogin(self)
        self.previous_state: tp.Optional[tp.Type[State]] = None
        self._state_thread_list: tp.List[threading.Thread] = []

    @property
    def _state_thread(self) -> tp.Optional[threading.Thread]:
        return self._state_thread_list[-1] if self._state_thread_list else None

    @_state_thread.setter
    def _state_thread(self, state_thread: threading.Thread) -> None:
        self._state_thread_list.append(state_thread)
        thread_list = self._state_thread_list
        logger.debug(
            f"Attribute _state_thread_list of WorkBench is now of len {len(thread_list)}\n"
            f"Threads alive: {list(filter(lambda t: t.is_alive(), thread_list))}"
        )

    @property
    def camera(self) -> tp.Optional[Camera]:
        return self._associated_camera

    @property
    def unit_in_operation(self) -> tp.Optional[str]:
        return str(self.associated_unit.internal_id) if self.associated_unit else None

    @property
    def is_operation_ongoing(self) -> bool:
        return bool(self.unit_in_operation)

    @property
    def state_name(self) -> str:
        return self.state.name

    @property
    def ip(self) -> tp.Optional[str]:
        try:
            return str(self._workbench_config["api socket"].split(":")[0])
        except Exception as E:
            logger.error(E)
            return None

    @property
    def state_description(self) -> str:
        return str(self.state.description)

    def _get_camera(self) -> tp.Optional[Camera]:
        camera_config: tp.Optional[ConfigSection] = self._workbench_config["hardware"]["camera"]
        return Camera(camera_config) if camera_config else None

    def apply_state(self, state: tp.Type[State], *args: tp.Any, **kwargs: tp.Any) -> None:
        """execute provided state in the background"""
        self.previous_state = self.state.__class__
        self.state = state(self)
        logger.info(f"Workbench state is now {self.state.name}")

        # execute state in the background
        thread_name: str = f"{self.state.name}-{randint(1, 999)}"
        logger.debug(f"Trying to execute state: {self.state.name} in thread {thread_name}")
        self._state_thread = threading.Thread(
            target=self.state.perform_on_apply,
            args=args,
            kwargs=kwargs,
            daemon=False,
            name=thread_name,
        )
        self._state_thread.start()
