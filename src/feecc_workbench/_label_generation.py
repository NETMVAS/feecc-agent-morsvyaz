import pathlib
import time
from datetime import datetime as dt
import barcode
from barcode.writer import ImageWriter

import qrcode
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from .config import CONFIG
from .utils import time_execution

# color values
color = tuple[int, int, int]
WHITE: color = (255, 255, 255)
BLACK: color = (0, 0, 0)


@time_execution
def _resize_to_paper_aspect_ratio(image: Image) -> Image:
    """expand image to fit the paper aspect ratio"""
    label_w, label_h = [int(x) for x in CONFIG.printer.paper_aspect_ratio.split(":")]
    or_img_w, or_img_h = image.size
    if or_img_w / or_img_h >= label_w / label_h:
        tar_img_w: int = or_img_w
        tar_img_h: int = int(label_h * or_img_w / label_w)
    else:
        tar_img_w: int = int(label_w * or_img_h / label_h)
        tar_img_h: int = or_img_h

    resized_image: Image = Image.new(mode="RGB", size=(tar_img_w, tar_img_h), color=(255, 255, 255))
    resized_image.paste(image, (int((tar_img_w - or_img_w) / 2), int((tar_img_h - or_img_h) / 2)))
    return resized_image


@time_execution
def create_qr(link: str) -> pathlib.Path:
    """This is a qr-creating submodule. Inserts a Robonomics logo inside the qr and adds logos aside if required"""
    logger.debug(f"Generating QR code image file for {link}")

    qr: Image = qrcode.make(link, border=1)
    qr = _resize_to_paper_aspect_ratio(qr)
    logger.debug(f"QR size: {qr.size}")

    dir_ = pathlib.Path("output/qr_codes")

    if not dir_.is_dir():
        dir_.mkdir()

    filename = f"{int(time.time())}_qr.png"
    path_to_qr = pathlib.Path(dir_ / filename)
    qr.save(path_to_qr)  # saving picture for further printing with a timestamp

    logger.debug(f"Successfully saved QR code image file for {link} to {path_to_qr}")

    return path_to_qr


@time_execution
def create_seal_tag() -> pathlib.Path:
    """generate a custom seal tag with required parameters"""
    logger.info("Generating seal tag")

    timestamp_enabled: bool = CONFIG.printer.security_tag_add_timestamp
    tag_timestamp: str = dt.now().strftime("%d.%m.%Y")
    dir_ = pathlib.Path("output/seal_tags")

    if not dir_.is_dir():
        dir_.mkdir()

    seal_tag_path = dir_ / pathlib.Path(f"seal_tag_{tag_timestamp}.png" if timestamp_enabled else "seal_tag_base.png")

    # check if seal tag has already been created
    if seal_tag_path.exists():
        return seal_tag_path

    # make a basic security tag with needed dimensions
    image_height = 200
    image_width = 554
    seal_tag_image = Image.new(mode="RGB", size=(image_width, image_height), color=WHITE)
    seal_tag_draw = ImageDraw.Draw(seal_tag_image)

    # specify fonts
    font_path = "media/helvetica-cyrillic-bold.ttf"
    font_size: int = 52
    font = ImageFont.truetype(font=font_path, size=font_size)

    # add text to the image
    upper_field: int = 30
    text = "ОПЛОМБИРОВАНО"
    main_txt_w, main_txt_h = seal_tag_draw.textsize(text, font)
    x: int = int((image_width - main_txt_w) / 2)
    seal_tag_draw.text(xy=(x, upper_field), text=text, fill=BLACK, font=font, align="center")

    # add a timestamp to the seal tag if needed
    if timestamp_enabled:
        txt_w, _ = seal_tag_draw.textsize(tag_timestamp, font)
        xy: tuple[int, int] = int((image_width - txt_w) / 2), (upper_field + main_txt_h)
        seal_tag_draw.text(xy=xy, text=tag_timestamp, fill=BLACK, font=font, align="center")

    # save the image in the output folder
    seal_tag_image = _resize_to_paper_aspect_ratio(seal_tag_image)
    seal_tag_image.save(seal_tag_path)

    logger.debug(f"The seal tag has been generated and saved to {seal_tag_path}")

    # return a relative path to the image
    return seal_tag_path


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
        barcode_path = str(ean_code.save(self.basename, {"module_height": 12, "text_distance": 3, "font_size": 8, "quiet_zone": 1}))
        with Image.open(barcode_path) as img:
            img = _resize_to_paper_aspect_ratio(img)
            img.save(barcode_path)

        return barcode_path
