import asyncio
import os
import sys
import typing as tp

from loguru import logger

from .Config import Config
from .Employee import Employee
from .Singleton import SingletonMeta
from .Types import GlobalConfig
from .Unit import Unit
from .WorkBench import WorkBench
from .database import MongoDbWrapper
from .exceptions import EmployeeNotFoundError, UnitNotFoundError, WorkbenchNotFoundError


class Hub(metaclass=SingletonMeta):
    """
    Hub is the class on top of the object hierarchy that handles
    operating the workbenches and is meant to be initialized only once
    """

    def __init__(self) -> None:
        logger.info("Initialized an instance of hub")
        self._config: GlobalConfig = Config().global_config
        self.database: MongoDbWrapper = self._get_database()
        self._employees: tp.Dict[str, Employee] = asyncio.run(self._get_employees())
        self._workbench: WorkBench = WorkBench(Config().workbench_config)
        self._create_dirs()

    @staticmethod
    def _create_dirs() -> None:
        if not os.path.isdir("output"):
            os.mkdir("output")

    def get_workbench_number_by_ip(self, ip_address: str) -> tp.Optional[int]:
        """find the provided ip in the config and return the workbench number for it"""
        return self._workbench.number if self._workbench.ip == ip_address else None

    def authorize_employee(self, employee_card_id: str, workbench_no: int) -> None:
        """logs the employee in at a given workbench"""
        try:
            employee: Employee = self._employees[employee_card_id]
        except KeyError:
            raise EmployeeNotFoundError(f"Rfid card ID {employee_card_id} unknown")

        workbench: WorkBench = self.get_workbench_by_number(workbench_no)
        workbench.state.start_shift(employee)

    def _get_database(self) -> MongoDbWrapper:
        """establish MongoDB connection and initialize the wrapper"""

        try:
            mongo_connection_url_env: tp.Optional[str] = os.environ["MONGO_CONNECTION_URL"]

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

    async def _get_employees(self) -> tp.Dict[str, Employee]:
        """load up employee database and initialize an array of Employee objects"""
        employee_list = await self.database.get_all_employees()
        return {employee.rfid_card_id: employee for employee in employee_list}

    def get_workbench_by_number(self, workbench_no: int) -> WorkBench:
        """find the workbench with the provided number"""
        if self._workbench.number == workbench_no:
            return self._workbench

        message: str = f"Could not find the workbench with number {workbench_no}. Does it exist?"
        logger.error(message)
        raise WorkbenchNotFoundError(message)

    async def create_new_unit(self, unit_type: str) -> str:
        """initialize a new instance of the Unit class"""
        unit = Unit(self._config, unit_type)
        await self.database.upload_unit(unit)

        if unit.internal_id is not None:
            return unit.internal_id
        else:
            raise ValueError("Unit internal_id is None")

    def get_employee_by_card_id(self, card_id: str) -> Employee:
        """find the employee with the provided RFID card id"""
        if card_id not in self._employees:
            raise EmployeeNotFoundError(f"No employee with card ID {card_id}")

        return self._employees[card_id]

    async def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
        """find the unit with the provided internal id"""
        try:
            return await self.database.get_unit_by_internal_id(unit_internal_id, self._config)

        except Exception as E:
            logger.error(E)
            message: str = f"Could not find the Unit with int. id {unit_internal_id}. Does it exist?"
            raise UnitNotFoundError(message)
