import pathlib

import barcode
from barcode.writer import ImageWriter


class Barcode:
    def __init__(self, unit_code: str) -> None:
        self.unit_code: str = unit_code
        self.barcode: barcode.EAN13 = barcode.get("ean13", self.unit_code, writer=ImageWriter())
        self.basename: str = f"output/barcode/{self.barcode.get_fullcode()}_barcode"
        self.filename: str = f"{self.basename}.png"
        self.save_barcode(self.barcode)

    def save_barcode(self, ean_code: barcode.EAN13) -> str:
        """Method that saves the barcode image"""
        dir_ = pathlib.Path(self.filename).parent
        if not dir_.is_dir():
            dir_.mkdir(parents=True)
        return str(ean_code.save(self.basename, {"module_height": 8, "text_distance": 3, "font_size": 8}))
