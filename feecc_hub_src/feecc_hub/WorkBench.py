from __future__ import annotations

import os
import sys
import threading
import typing as tp
from random import randint

from loguru import logger

from .Config import Config
from .Employee import Employee
from .Singleton import SingletonMeta
from .Types import GlobalConfig, WorkbenchConfig
from .Unit import Unit
from ._State import AwaitLogin, State
from .database import MongoDbWrapper


class WorkBench(metaclass=SingletonMeta):
    """
    Work bench is a union of an Employee, working at it and Camera attached.
    It provides highly abstract interface for interaction with them
    """

    def __init__(self) -> None:
        self._workbench_config: WorkbenchConfig = Config().workbench_config
        self.number: int = self._workbench_config["workbench number"]
        self.camera: tp.Dict[str, tp.Any] = self._workbench_config["hardware"]["camera"]
        self.ip: str = self._workbench_config["api socket"].split(":")[0]
        self.employee: tp.Optional[Employee] = None
        self.associated_unit: tp.Optional[Unit] = None
        logger.info(f"Workbench {self.number} was initialized")
        self.state: State = AwaitLogin(self)
        self.previous_state: tp.Optional[tp.Type[State]] = None
        self._state_thread_list: tp.List[threading.Thread] = []
        self._config: GlobalConfig = Config().global_config
        self.database: MongoDbWrapper = self._get_database()

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
    def unit_in_operation(self) -> tp.Optional[str]:
        return str(self.associated_unit.internal_id) if self.associated_unit else None

    @property
    def is_operation_ongoing(self) -> bool:
        return bool(self.unit_in_operation)

    @property
    def state_name(self) -> str:
        return self.state.name

    @property
    def state_description(self) -> str:
        return str(self.state.description)

    @property
    def ipv4(self) -> str:
        return str(self._workbench_config["api socket"].split(":")[0])

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

    async def authorize_employee(self, employee_card_id: str) -> None:
        """logs the employee in at a given workbench"""
        employee: Employee = await self.database.get_employee_by_card_id(employee_card_id)
        self.state.start_shift(employee)

    def _get_database(self) -> MongoDbWrapper:
        """establish MongoDB connection and initialize the wrapper"""

        try:
            mongo_connection_url_env: tp.Optional[str] = os.getenv("MONGO_CONNECTION_URL")

            if mongo_connection_url_env is None:
                mongo_connection_url: str = self._config["mongo_db"]["mongo_connection_url"]
            else:
                mongo_connection_url = mongo_connection_url_env

            wrapper: MongoDbWrapper = MongoDbWrapper(mongo_connection_url)
            return wrapper

        except Exception as E:
            message: str = f"Failed to establish database connection: {E}. Exiting."
            logger.critical(message)
            sys.exit(1)

    async def create_new_unit(self, unit_type: str) -> str:
        """initialize a new instance of the Unit class"""
        unit = Unit(self._config, unit_type)
        await self.database.upload_unit(unit)

        if unit.internal_id is not None:
            return unit.internal_id
        else:
            raise ValueError("Unit internal_id is None")
