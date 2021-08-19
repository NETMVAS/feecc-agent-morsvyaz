import sys
import typing as tp

import yaml
from loguru import logger

from .Singleton import SingletonMeta
from .Types import GlobalConfig, WorkbenchConfig


class Config(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self.global_config: GlobalConfig = self._load_config("config/hub_config.yaml")  # type: ignore
        self.workbench_config: WorkbenchConfig = self._load_config("config/workbench_config.yaml")  # type: ignore

    @staticmethod
    def _load_config(config_path: str) -> tp.Union[GlobalConfig, WorkbenchConfig]:
        """
        :return: dictionary containing all the configurations
        :rtype: dict

        Reading config, containing all the required data
        camera parameters (ip, login, password, port), etc
        """
        logger.debug(f"Looking for config in {config_path}")

        try:
            with open(config_path) as f:
                content = f.read()
                config_f: GlobalConfig = yaml.load(content, Loader=yaml.FullLoader)
                return config_f

        except Exception as E:
            logger.error(f"Error parsing configuration file {config_path}: {E}")
            sys.exit(1)
