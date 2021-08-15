from brother_ql import BrotherQLRaster, conversion
from brother_ql.backends.helpers import send
from loguru import logger
from PIL import Image

from .Types import Config, ConfigSection


class PrinterTask:
    """a printing task for the label printer. executed at init"""

    def __init__(self, image_path: str, config: Config) -> None:
        self._config: ConfigSection = config["printer"]
        self._address: str = str(self._config["address"])
        self._paper_width: str = str(self._config["paper_width"])
        self._model: str = str(self._config["printer_model"])
        self._image_path: str = image_path

        if self._config["enable"]:
            self._print_task()
        else:
            logger.info("Printer disabled in config. Task dropped.")

    def _print_task(self) -> None:
        """execute the task"""
        logger.info(f"Printing task created for image {self._image_path}")
        image: Image = self._get_image(self._image_path)
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
        red: bool = self._paper_width == "62"
        conversion.convert(qlr, [image], self._paper_width, red=red)
        send(qlr.data, self._address)
