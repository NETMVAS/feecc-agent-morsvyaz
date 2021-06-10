import logging
from abc import ABC, abstractmethod
import typing as tp

from Agent import Agent
from Camera import Camera
from Barcode import Barcode


class Factory(ABC):
    """Factory ABC class for creating various instances"""

    @abstractmethod
    def new_instance(self, **kwargs) -> tp.NoReturn:
        raise NotImplementedError


class AgentFactory(Factory):
    """Agent Factory class for creating various Agent instances"""

    def new_instance(self, config: tp.Dict[str, tp.Dict[str, tp.Any]], camera_config: tp.Dict[str, tp.Any]):
        logging.info(f"Created new Agent instance")
        return Agent(config, camera_config)


class CameraFactory(Factory):
    """Camera Factory class for creating various Camera instances"""

    def new_instance(self, config: tp.Dict[str, str]):
        logging.info(f"Created new Camera instance")
        return Camera(config)


class BarcodeFactory(Factory):
    """Barcode Factory for creating various Barcode instances"""

    def new_instance(self, unit_code: str):
        logging.info(f"Created new Barcode instance")
        return Barcode(unit_code)
