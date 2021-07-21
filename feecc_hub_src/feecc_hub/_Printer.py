import logging
import typing as tp

from PIL import Image
from brother_ql import BrotherQLRaster, conversion
from brother_ql.backends.helpers import send


class Task:
    """a printing task for the label printer"""

    def __init__(self, picname: str, config: tp.Dict[str, tp.Dict[str, tp.Any]]) -> None:
        """
        :param picname: path to a picture to be printed
        :type picname: str

        When creating an instance of the class, it creates a task for a brother QL-800 printer to print a label with a
        qr-code passed as an argument. picname != qrpic, it contains side fields and logos (optionally)
        """
        logging.info("Initializing printer")
        logging.debug(f"picname: {picname}, config for printer: {config['printer']}")

        image = Image.open(picname)

        printer_config: tp.Dict[str, tp.Any] = config["printer"]
        printer: str = printer_config["address"]  # link to device
        label_name = str(printer_config["paper_width"])  # that depends on paper used for printing

        # resize the image before printing
        w, h = image.size
        target_w = 696 if label_name == "62" else 554
        target_h = int(h * (target_w / w))
        image = image.resize((target_w, target_h))
        logging.info(f"Printing image of size {image.size}")

        qlr = BrotherQLRaster(printer_config["printer_model"])
        red: bool = label_name == "62"
        logging.debug("Attempting image conversion")
        conversion.convert(qlr, [image], label_name, red=red)
        logging.debug("Sending task to printer")
        send(qlr.data, printer)
        # this is some standard code for printing with brother label printer with python,
        # red = True means that black and red printing will be done. Only for 62 label paper
        logging.info("Printed")
