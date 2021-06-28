import logging
import os
import typing as tp

import barcode
from barcode.writer import ImageWriter

from ._Printer import Task


class Barcode:
    def __init__(self, unit_code: str) -> None:
        self.unit_code: str = unit_code
        self.filename: tp.Optional[str] = None

        try:
            self.barcode: barcode.EAN13 = self.generate_barcode(unit_code)
            self.barcode_path: str = self.save_barcode(self.barcode)
        except Exception as E:
            logging.error(f"Barcode error: {E}")

    def generate_barcode(self, int_id: str) -> barcode.EAN13:
        """
        Method used to generate EAN13 class

        Args:
            int_id (str): value which will be on barcode

        Returns:
            EAN13 Class
        """
        self.filename = f"output/barcode/{int_id}_barcode"
        return barcode.get("ean13", int_id, writer=ImageWriter())

    def save_barcode(self, ean_code: barcode.EAN13) -> str:
        """
        Method that saves barcode picture

        Args:
            ean_code (EAN13): EAN13 barcode class
        Returns:
            Path to barcode .png file
        """
        dir_: tp.Optional[str] = os.path.dirname(self.filename)
        if not os.path.isdir(dir_):
            os.mkdir(dir_)

        filename: str = ean_code.save(
            self.filename, {"module_height": 8, "text_distance": 1, "font_size": 14}
        )
        logging.info(f"Barcode {ean_code.get_fullcode()} was saved to {filename}")

        return filename

    def print_barcode(self, config: tp.Dict[str, tp.Dict[str, tp.Any]]) -> None:
        try:
            Task(f"{self.filename}.png", config)
        except Exception as E:
            logging.error(f"Failed to print barcode: {E}")
