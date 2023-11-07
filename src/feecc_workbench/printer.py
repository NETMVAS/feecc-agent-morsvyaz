import os
import textwrap
from pathlib import Path
from statistics import mean
from string import ascii_letters

import cups
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

from .config import CONFIG
from .Messenger import messenger
from .translation import translation
from .utils import async_time_execution
from ._label_generation import _resize_to_paper_aspect_ratio


async def print_image(file_path: Path, annotation: str | None = None) -> None:
    """print the provided image file"""
    if not CONFIG.printer.enable:
        logger.warning("Printer disabled, task dropped")
        return

    assert file_path.exists(), f"Image file {file_path} doesn't exist"
    assert file_path.is_file(), f"{file_path} is not an image file"

    try:
        if annotation:
            image: Image = Image.open(file_path)
            image = _annotate_image(image, annotation)
            image = _resize_to_paper_aspect_ratio(image)
            image.save(file_path)
    except Exception as e:
        logger.error(f"Error annotating image: {e}")

    task = _print_image_task(file_path)
    logger.info(f"Printing {annotation}")
    await task


@async_time_execution
async def _print_image_task(file_path: Path) -> None:
    """print image via cups"""

    try:
        cups.setUser("feecc")
        conn: cups.Connection = cups.Connection()
        printer_name: str = list(conn.getPrinters().keys())[0]
        print_id: int = conn.printFile(printer_name, str(Path.absolute(file_path)), file_path.stem, {})
        logger.info(f"Printed image '{file_path=}', {print_id=}")
    except Exception as e:
        logger.error(f"Print task failed: {e}")
        messenger.error(translation('PrintError'))


def _annotate_image(image: Image, text: str) -> Image:
    """add an annotation to the bottom of the image"""
    # wrap the message
    font_path = "media/helvetica-cyrillic-bold.ttf"
    assert os.path.exists(font_path), f"Cannot open font at {font_path=}. No such file."
    font: FreeTypeFont = ImageFont.truetype(font_path, 35)
    avg_char_width: float = mean((font.getsize(char)[0] for char in ascii_letters))
    img_w, img_h = image.size
    logger.debug(f"Image size before annotation: {img_w, img_h}")
    max_chars_in_line: int = int(img_w * 0.95 / avg_char_width)
    wrapped_text: str = textwrap.fill(text, max_chars_in_line)

    # get message size
    sample_draw: ImageDraw.Draw = ImageDraw.Draw(image)
    _, txt_h = sample_draw.textsize(wrapped_text, font)
    # https://stackoverflow.com/questions/59008322/pillow-imagedraw-text-coordinates-to-center/59008967#59008967
    txt_h += font.getoffset(text)[1]

    # draw the message
    annotated_image: Image = Image.new(mode="RGB", size=(img_w, img_h + txt_h + 5), color=(255, 255, 255))
    annotated_image.paste(image, (0, txt_h + 5))
    new_img_w, new_img_h = annotated_image.size
    txt_draw: ImageDraw.Draw = ImageDraw.Draw(annotated_image)
    text_pos: (int, int) = (
        int(new_img_w / 2),
        int((new_img_h - img_h) / 2),
    )
    txt_draw.text(
        text_pos,
        wrapped_text,
        font=font,
        fill=(0, 0, 0),
        anchor="mm",
        align="center",
    )

    return annotated_image
