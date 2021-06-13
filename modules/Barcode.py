import logging

import barcode
import csv
import os
import typing as tp

from Printer import Task

# set up logging
logging.basicConfig(
    level=logging.INFO, filename="agent.log", format="%(asctime)s %(levelname)s: %(message)s"
)


class Barcode:
    def __init__(self, unit_code: str):
        self.matching_table_path = "matching_table.csv"
        self.unit_code = unit_code

        try:
            self.barcode = self.generate_barcode(unit_code)
            self.barcode_path = self.save_barcode(self.barcode)
            print(self.barcode_path)
        except Exception as E:
            logging.error(f"Barcode error: {E}")

    @staticmethod
    def generate_barcode(num: str) -> barcode.EAN13:
        """
        Method used to generate EAN13 class

        Args:
            num (int): value which will be on barcode

        Returns:
            EAN13 Class
        """
        return barcode.get("ean13", num)

    @staticmethod
    def save_barcode(ean_code: barcode.EAN13, dir_path: str = "barcode") -> str:
        """
        Method that saves barcode picture

        Args:
            ean_code (EAN13): EAN13 barcode class
            dir_path (str): Where barcode will be saved

        Returns:
            Path to barcode .svg file
        """
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)

        filename = ean_code.save(dir_path + "/" + str(ean_code))

        logging.info(f"Barcode {ean_code.get_fullcode()} was saved to {filename}")

        return filename

    @staticmethod
    def print_barcode(barcode_path: str, config: tp.Dict[str, tp.Dict[str, tp.Any]]) -> None:
        try:
            Task(barcode_path, config)
        except Exception as E:
            logging.error(f"Failed to print barcode: {E}")

    def _load_csv(self) -> tp.Dict[str, str]:
        matching_table = {}

        with open(self.matching_table_path, newline="") as f:
            reader = csv.reader(f, delimiter=";")
            for key, val in reader:
                matching_table[key] = val

        return matching_table
