import logging
import os
import typing as tp

import barcode
from barcode.writer import ImageWriter

from ._Printer import Task


class Barcode:
    def __init__(self, unit_code: str):
        self.matching_table_path = "matching_table.csv"
        self.unit_code = unit_code
        self.filename: tp.Optional[str] = None

        try:
            self.barcode = self.generate_barcode(unit_code)
            self.barcode_path = self.save_barcode(self.barcode)
        except Exception as E:
            logging.error(f"Barcode error: {E}")

    def generate_barcode(self, int_id: str) -> barcode.EAN13:
        """
        Method used to generate EAN13 class

        Args:
            num (int): value which will be on barcode

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

        dir_: str = os.path.dirname(self.filename)
        if not os.path.isdir(dir_):
            os.mkdir(dir_)

        filename = ean_code.save(self.filename)
        logging.info(f"Barcode {ean_code.get_fullcode()} was saved to {filename}")

        return filename

    @staticmethod
    def print_barcode(barcode_path: str, config: tp.Dict[str, tp.Dict[str, tp.Any]]) -> None:
        try:
            Task(f"{self.filename}.png", config)
        except Exception as E:
            logging.error(f"Failed to print barcode: {E}")

    def _load_csv(self) -> tp.Dict[str, str]:
        matching_table = {}

        with open(self.matching_table_path, newline="") as f:
            reader = csv.reader(f, delimiter=";")
            for key, val in reader:
                matching_table[key] = val

        return matching_table
