import logging
import shelve
import sys
import typing as tp

import yaml

from .Unit import Unit
from .WorkBench import WorkBench
from ._Types import Config


class Hub:
    """
    Hub is the class on top of the object hierarchy that handles
    operating the workbenches and is meant to be initialized only once
    """

    def __init__(self) -> None:
        self.config: Config = self._get_config()
        self._workbenches: tp.List[WorkBench] = self._initialize_workbenches()
        self._units: tp.List[Unit] = self._unshelve_units()

    @staticmethod
    def _get_config(config_path: str = "config/hub_config.yaml") -> tp.Any:
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
                config_f: tp.Dict[str, tp.Dict[str, tp.Any]] = yaml.load(content, Loader=yaml.FullLoader)
                logging.debug(f"Configuration dict: {content}")
                return config_f
        except Exception as E:
            logging.error(f"Error parsing configuration file {config_path}:\n{E}")
            sys.exit(1)

    def end_session(self) -> None:
        """a method to execute when daemon exits"""

        self._dump_open_units()

    def get_workbench_by_number(self, workbench_no: int) -> tp.Union[WorkBench, None]:
        """find the workbench with the provided number"""

        for workbench in self._workbenches:
            if workbench.number == workbench_no:
                return workbench

        logging.error(f"Could not find the workbench with number {workbench_no}. Does it exist?")
        return None

    def create_new_unit(self) -> str:
        """initialize a new instance of the Unit class"""

        unit = Unit(self.config)
        self._units.append(unit)
        return unit.internal_id

    def get_unit_by_internal_id(self, unit_internal_id: str) -> tp.Union[Unit, None]:
        """find the unit with the provided internal id"""

        for unit in self._units:
            if unit.internal_id == unit_internal_id:
                return unit

        logging.error(f"Could not find the Unit with int. id {unit_internal_id}. Does it exist?")
        return None

    def _initialize_workbenches(self) -> tp.List[WorkBench]:
        """make all the WorkBench objects using data specified in workbench_config.yaml"""

        workbench_config: tp.List[tp.Dict[str, tp.Any]] = self._get_config("config/workbench_config.yaml")
        workbenches = []

        for workbench in workbench_config:
            workbench_object = WorkBench(self, workbench)
            workbenches.append(workbench_object)

        if not workbenches:
            logging.critical("No workbenches could be spawned using 'workbench_config.yaml'. Can't operate. Exiting.")
            sys.exit(1)

        return workbenches

    @staticmethod
    def _unshelve_units(shelve_path: str = "config/Unit.shelve") -> tp.List[Unit]:
        """initialize a Unit object for every unfinished Unit using it's data files"""

        try:
            with shelve.open(shelve_path) as unit_shelve:
                units: tp.List[Unit] = unit_shelve["unfinished_units"]

            logging.info(f"Unshelved {len(units)} from {shelve_path}")
            logging.debug(units)
            return units

        except Exception as e:
            logging.error(f"An error occurred during unshelving units from {shelve_path}:\n{e}")
            return []

    def _dump_open_units(self, shelve_path: str = "config/Unit.shelve") -> None:
        """shelve every unfinished Unit"""

        if not len(self._units):
            logging.info("Shelving stopped: no units to shelve.")

        try:
            logging.info(f"Shelving {len(self._units)} to {shelve_path}")
            with shelve.open(shelve_path) as unit_shelve:
                unit_shelve["unfinished_units"] = self._units
            logging.info(f"Successfully shelved {len(self._units)} units to {shelve_path}")

        except Exception as e:
            logging.error(f"An error occurred during shelving units to {shelve_path}:\n{e}")
