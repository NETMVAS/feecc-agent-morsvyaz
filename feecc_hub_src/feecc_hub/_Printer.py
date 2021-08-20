import re
import typing as tp
from subprocess import check_output

from PIL import Image
from brother_ql import BrotherQLRaster, conversion
from brother_ql.backends.helpers import send
from loguru import logger

from .Singleton import SingletonMeta
from .Types import ConfigSection, GlobalConfig


class Printer(metaclass=SingletonMeta):
    """a printing task for the label printer. executed at init"""

    def __init__(self, config: tp.Optional[GlobalConfig] = None) -> None:
        self._config: ConfigSection = config["printer"] if config else {}
        self._paper_width: str = str(self._config["paper_width"])
        self._model: str = str(self._config["printer_model"])
        self._address: str = self._get_usb_address()

    @property
    def _enabled(self) -> bool:
        """check if device is enabled in config"""
        return bool(self._config["enable"])

    @property
    def _connected(self) -> bool:
        """check if device is on the USB bus"""
        try:
            command: str = f'lsusb | grep "{self._model}" -o'
            return bool(check_output(command, shell=True, text=True))
        except Exception as E:
            logger.debug(f"An error occurred while checking if device is connected: {E}")
            return False

    def _get_usb_address(self) -> str:
        """Get printer USB bus address"""
        try:
            command: str = f'lsusb | grep "{self._model}"'
            output: str = check_output(command, shell=True, text=True)
            addresses: tp.List[str] = re.findall("[0-9a-fA-F]{4}:[0-9a-fA-F]{4}", output)
            address: tp.List[str] = addresses[0].split(":")
            bus_address: str = f"usb://0x{address[0]}:0x{address[1]}"
            return bus_address
        except Exception as E:
            logger.error(f"An error occurred while parsing address: {E}")
            return ""

    def print_image(self, image_path: str) -> None:
        """execute the task"""
        if not all((self._enabled, self._connected)):
            logger.info("Printer disabled in config or disconnected. Task dropped.")
            return
        logger.info(f"Printing task created for image {image_path}")
        image: Image = self._get_image(image_path)
        self._print_image(image)
        logger.info("Printing task done")

    def _get_image(self, image_path: str) -> Image:
        """prepare and resize the image before printing"""
        image = Image.open(image_path)
        w, h = image.size
        target_w = 696 if self._paper_width == "62" else 554
        target_h = int(h * (target_w / w))
        image = image.resize((target_w, target_h))
        return image

    def _print_image(self, image: Image) -> None:
        """print provided image"""
        logger.info(f"Printing image of size {image.size}")
        qlr: BrotherQLRaster = BrotherQLRaster(self._model)
        red: bool = self._config["red"]
        conversion.convert(qlr, [image], self._paper_width, red=red)
        send(qlr.data, self._address)
