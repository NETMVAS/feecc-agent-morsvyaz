import re
import textwrap
import typing as tp
from statistics import mean
from string import ascii_letters
from subprocess import check_output

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
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

    def print_image(self, image_path: str, annotation: tp.Optional[str] = None) -> None:
        """execute the task"""
        if not self._address:
            self._address = self._get_usb_address()

        if not all((self._enabled, self._connected)):
            logger.info("Printer disabled in config or disconnected. Task dropped.")
            return
        logger.info(f"Printing task created for image {image_path}")
        image: Image = self._get_image(image_path)

        if annotation is not None:
            image = self._annotate_image(image, annotation)

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

    @staticmethod
    def _annotate_image(image: Image, text: str) -> Image:
        """add an annotation to the bottom of the image"""
        # wrap the message
        font: FreeTypeFont = ImageFont.truetype("feecc_hub/fonts/helvetica-cyrillic-bold.ttf", 24)
        avg_char_width: float = mean((font.getsize(char)[0] for char in ascii_letters))
        img_w, img_h = image.size
        max_chars_in_line: int = int(img_w * 0.95 / avg_char_width)
        wrapped_text: str = textwrap.fill(text, max_chars_in_line)

        # get message size
        sample_draw: ImageDraw.Draw = ImageDraw.Draw(image)
        _, txt_h = sample_draw.textsize(wrapped_text, font)
        # https://stackoverflow.com/questions/59008322/pillow-imagedraw-text-coordinates-to-center/59008967#59008967
        txt_h += font.getoffset(text)[1]

        # draw the message
        annotated_image: Image = Image.new(mode="RGB", size=(img_w, img_h + txt_h + 5), color=(255, 255, 255))
        annotated_image.paste(image, (0, 0))
        new_img_w, new_img_h = annotated_image.size
        txt_draw: ImageDraw.Draw = ImageDraw.Draw(annotated_image)
        text_pos: tp.Tuple[int, int] = (int(new_img_w / 2), int((new_img_h - img_h) / 2 + img_h))
        txt_draw.text(text_pos, wrapped_text, font=font, fill=(0, 0, 0), anchor="mm", align="center")

        return annotated_image
