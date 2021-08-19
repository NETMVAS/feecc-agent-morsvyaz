import os
import time
import typing as tp
from datetime import datetime as dt

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .Types import GlobalConfig

# color values
color = tp.Tuple[int, int, int]
WHITE: color = (255, 255, 255)
BLACK: color = (0, 0, 0)


def create_qr(link: str, config: GlobalConfig) -> str:
    """
    :param link: full yourls url. E.g. url.today/6b
    :type link: str
    :param config: dictionary containing all the configurations
    :type config: dict
    :return: full filename of a resulted qr-code
    :rtype: str

    This is a qr-creating submodule. Inserts a Robonomics logo inside the qr and adds logos aside if required
    """
    robonomics_logo = Image.open("media/robonomics.jpg").resize((100, 100))
    qr_big = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr_big.add_data("https://" + link)
    qr_big.make()
    img_qr_big = qr_big.make_image().convert("RGB")

    pos = (
        (img_qr_big.size[0] - robonomics_logo.size[0]) // 2,
        (img_qr_big.size[1] - robonomics_logo.size[1]) // 2,
    )  # position to insert to logo right in the center of a qr-code

    qr_size = 200  # size of the entire qr-code
    border_s = int((554 - qr_size) / 2)
    img_qr_big.paste(robonomics_logo, pos)  # insert logo
    img_qr_big = img_qr_big.resize((qr_size, qr_size))  # resize qr
    img_qr_big = ImageOps.expand(img_qr_big, border=border_s, fill="white")
    img_qr_pos = 0, border_s - 2, qr_size + border_s * 2, border_s + qr_size + 2
    img_qr_big = img_qr_big.crop(img_qr_pos)

    if config["print_qr"]["logos"]:
        left_pic = Image.open("media/left_pic.jpg").resize((qr_size, qr_size))
        posl = (24, 2)
        img_qr_big.paste(left_pic, posl)

        right_pic = Image.open("media/right_pic.jpg").resize((qr_size, qr_size))
        posr = (696 - qr_size - 24, 2)
        img_qr_big.paste(right_pic, posr)
    # this is used to paste logos if needed. Position is set empirically so that logos are aside of the qr-code
    dir_ = "output/qr_codes"

    if not os.path.isdir(dir_):
        os.mkdir(dir_)

    path_to_qr = dir_ + f"/{int(time.time())}_qr.png"
    img_qr_big.save(path_to_qr)  # saving picture for further printing with a timestamp

    return path_to_qr


def create_seal_tag(config: GlobalConfig) -> str:
    """generate a custom seal tag with required parameters"""
    timestamp_enabled: bool = config["print_security_tag"]["enable_timestamp"]
    tag_timestamp: str = dt.now().strftime("%d.%m.%Y")
    dir_: str = "output/seal_tags"

    if not os.path.isdir(dir_):
        os.mkdir(dir_)

    seal_tag_path = f"{dir_}/seal_tag_{tag_timestamp}.png" if timestamp_enabled else f"{dir_}/seal_tag_base.png"

    # check if seal tag has already been created
    if os.path.exists(seal_tag_path):
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
        xy: tp.Tuple[int, int] = int((image_width - txt_w) / 2), (upper_field + main_txt_h)
        seal_tag_draw.text(xy=xy, text=tag_timestamp, fill=BLACK, font=font, align="center")

    # save the image in the output folder
    seal_tag_image.save(seal_tag_path)

    # return a relative path to the image
    return seal_tag_path
