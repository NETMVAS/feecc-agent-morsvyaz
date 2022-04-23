import typing as tp

import httpx
from loguru import logger

from .config import CONFIG
from .utils import get_headers, time_execution

PRINT_SERVER_ADDRESS: str = CONFIG.printer.print_server_uri


@time_execution
async def print_image(file_path: str, rfid_card_id: str, annotation: tp.Optional[str] = None) -> None:
    """print the provided image file"""
    if not CONFIG.printer.enable:
        logger.warning("Printer disabled, task dropped")
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{PRINT_SERVER_ADDRESS}/print_image"
        headers: tp.Dict[str, str] = get_headers(rfid_card_id)
        data = {"annotation": annotation}
        files = {"image_file": open(file_path, "rb")}
        response: httpx.Response = await client.post(url=url, headers=headers, data=data, files=files)

    if response.is_error:
        raise httpx.RequestError(response.text)

    logger.info(f"Printed image '{file_path}'")
