import logging
import sys
import typing as tp

import yaml

from .database import MongoDbWrapper
from .Employee import Employee
from .Unit import Unit
from .WorkBench import WorkBench
from ._Types import Config
from .exceptions import EmployeeNotFoundError, UnitNotFoundError, WorkbenchNotFoundError


class Hub:
    """
    Hub is the class on top of the object hierarchy that handles
    operating the workbenches and is meant to be initialized only once
    """

    def __init__(self) -> None:
        logging.info(f"Initialized an instance of hub {self}")
        self.config: Config = self._get_config()
        self.database: MongoDbWrapper = self._get_database()
        self._employees: tp.Dict[str, Employee] = self._get_employees()
        self._units: tp.List[Unit] = []
        self._workbenches: tp.List[WorkBench] = self._initialize_workbenches()

    def authorize_employee(self, employee_card_id: str, workbench_no: int) -> None:
        """logs the employee in at a given workbench"""
        try:
            employee: Employee = self._employees[employee_card_id]
        except KeyError:
            raise EmployeeNotFoundError(f"Rfid card ID {employee_card_id} unknown")

        workbench: WorkBench = self.get_workbench_by_number(workbench_no)
        workbench.start_shift(employee)

    def _get_database(self) -> MongoDbWrapper:
        """establish MongoDB connection and initialize the wrapper"""
        try:
            username: str = self.config["mongo_db"]["username"]
            password: str = self.config["mongo_db"]["password"]
            wrapper: MongoDbWrapper = MongoDbWrapper(username, password)
            return wrapper

        except Exception as e:
            message: str = f"Failed to establish database connection: {e}. Exiting."
            logging.critical(message)
            sys.exit()

    def _get_employees(self) -> tp.Dict[str, Employee]:
        """load up employee database and initialize an array of Employee objects"""
        employee_list = self.database.get_all_employees()
        employees: tp.Dict[str, Employee] = {}

        for employee in employee_list:
            employees[employee.rfid_card_id] = employee

        logging.info(f"Initialized {len(employees.keys())} employees")
        return employees

    @staticmethod
    def _get_config(config_path: str = "feecc_hub_src/config/hub_config.yaml") -> tp.Any:
        """
        :return: dictionary containing all the configurations
        :rtype: dict

        Reading config, containing all the required data, such as filepath, robonomics parameters (remote wss, seed),
        camera parameters (ip, login, password, port), etc
        """
        logging.debug(f"Looking for config in {config_path}")

        try:
            with open(config_path) as f:
                content = f.read()
                config_f: tp.Dict[str, tp.Dict[str, tp.Any]] = yaml.load(
                    content, Loader=yaml.FullLoader
                )
                return config_f

        except Exception as E:
            logging.error(f"Error parsing configuration file {config_path}: {E}")
            sys.exit(1)

    def get_workbench_by_number(self, workbench_no: int) -> WorkBench:
        """find the workbench with the provided number"""
        for workbench in self._workbenches:
            if workbench.number == workbench_no:
                return workbench

        message: str = f"Could not find the workbench with number {workbench_no}. Does it exist?"
        logging.error(message)
        raise WorkbenchNotFoundError(message)

    def create_new_unit(self, unit_type: str) -> str:
        """initialize a new instance of the Unit class"""
        unit = Unit(self.config, unit_type)
        self._units.append(unit)

        if unit.internal_id is not None:
            return unit.internal_id
        else:
            raise ValueError("Unit internal_id is None")

    def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
        """find the unit with the provided internal id"""
        for unit in self._units:
            if unit.internal_id == unit_internal_id:
                return unit

        message: str = f"Could not find the Unit with int. id {unit_internal_id}. Does it exist?"
        raise UnitNotFoundError(message)

    def _initialize_workbenches(self) -> tp.List[WorkBench]:
        """make all the WorkBench objects using data specified in workbench_config.yaml"""
        workbench_config: tp.List[tp.Dict[str, tp.Any]] = self._get_config(
            "feecc_hub_src/config/workbench_config.yaml"
        )
        workbenches = []

        for workbench in workbench_config:
            workbench_object = WorkBench(self, workbench)
            workbenches.append(workbench_object)

        if not workbenches:
            logging.critical(
                "No workbenches could be spawned using 'workbench_config.yaml'. Can't operate. Exiting."
            )
            sys.exit(1)

        return workbenches
