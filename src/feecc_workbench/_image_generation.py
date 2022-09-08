import pathlib
import time
from datetime import datetime as dt

import qrcode
from loguru import logger
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .config import CONFIG
from .utils import time_execution

# color values
color = tuple[int, int, int]
WHITE: color = (255, 255, 255)
BLACK: color = (0, 0, 0)


@time_execution
def create_qr(link: str) -> pathlib.Path:
    """This is a qr-creating submodule. Inserts a Robonomics logo inside the qr and adds logos aside if required"""
    logger.debug(f"Generating QR code image file for {link}")

    robonomics_logo = Image.open("media/robonomics.jpg").resize((100, 100))
    qr_big = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr_big.add_data(link)
    qr_big.make()
    img_qr_big = qr_big.make_image().convert("RGB")

    pos = (
        (img_qr_big.size[0] - robonomics_logo.size[0]) // 2,
        (img_qr_big.size[1] - robonomics_logo.size[1]) // 2,
    )  # position to insert to logo right in the center of a qr-code

    total_width = 554
    qr_size = total_width // 3  # size of the entire qr-code
    border_s = int((total_width - qr_size) / 2)
    img_qr_big.paste(robonomics_logo, pos)  # insert logo
    img_qr_big = img_qr_big.resize((qr_size, qr_size))  # resize qr
    img_qr_big = ImageOps.expand(img_qr_big, border=border_s, fill="white")
    img_qr_pos = 0, border_s - 2, qr_size + border_s * 2, border_s + qr_size + 2
    img_qr_big = img_qr_big.crop(img_qr_pos)

    # this is used to paste logos if needed. Position is set empirically so that logos are aside of the qr-code
    if CONFIG.printer.qr_add_logos:  # FIXME: Broken
        left_pic = Image.open("media/left_pic.jpg").resize((qr_size, qr_size))
        pos_l = (24, 2)
        img_qr_big.paste(left_pic, pos_l)

        right_pic = Image.open("media/right_pic.jpg").resize((qr_size, qr_size))
        pos_r = (total_width - qr_size - 24, 2)
        img_qr_big.paste(right_pic, pos_r)

    dir_ = pathlib.Path("output/qr_codes")

    if not dir_.is_dir():
        dir_.mkdir()

    filename = f"{int(time.time())}_qr.png"
    path_to_qr = pathlib.Path(dir_ / filename)
    img_qr_big.save(path_to_qr)  # saving picture for further printing with a timestamp

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
    seal_tag_image.save(seal_tag_path)

    logger.debug(f"The seal tag has been generated and saved to {seal_tag_path}")

    # return a relative path to the image
    return seal_tag_path
