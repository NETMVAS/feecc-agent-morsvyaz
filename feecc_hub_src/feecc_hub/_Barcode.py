import os

import barcode
from barcode.writer import ImageWriter


class Barcode:
    def __init__(self, unit_code: str) -> None:
        self.unit_code: str = unit_code
        self.barcode: barcode.EAN13 = barcode.get("ean13", self.unit_code, writer=ImageWriter())
        self.filename: str = f"output/barcode/{self.barcode.get_fullcode()}_barcode.png"
        self.save_barcode(self.barcode)

    def save_barcode(self, ean_code: barcode.EAN13) -> str:
        """Method that saves the barcode image"""
        dir_ = os.path.dirname(self.filename)
        if not os.path.isdir(dir_):
            os.makedirs(dir_)
        return ean_code.save(self.filename, {"module_height": 8, "text_distance": 1, "font_size": 14})
