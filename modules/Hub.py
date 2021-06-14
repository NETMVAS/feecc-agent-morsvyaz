from Types import Config
import logging
import yaml
import typing as tp
from WorkBench import WorkBench


class Hub:
    """
    Hub is the class on top of the object hierarchy that handles
    operating the workbenches and is meant to be initialized only once
    """

    def __init__(self) -> None:
        self.config: Config = self._get_config()
        self._workbenches: tp.List[WorkBench] = self._initialize_workbenches()

    @staticmethod
    def _get_config(config_path: str = "config/config.yaml") -> Config:
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
            logging.error(f"Error in configuration file! {E}")
            exit()

    def get_workbench_by_number(self, workbench_no: int) -> tp.Optional[WorkBench]:
        """find the get_workbench_by_number with the provided number"""

        for workbench in self._workbenches:
            if workbench.number == workbench_no:
                return workbench

        logging.error(f"Could not find get_workbench_by_number with number {workbench_no}. Does it exist?")
        return None

    # todo
    def _initialize_workbenches(self) -> tp.List[WorkBench]:
        pass
