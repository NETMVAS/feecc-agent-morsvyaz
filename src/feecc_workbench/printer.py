import asyncio
from pathlib import Path

import httpx
from loguru import logger

from .config import CONFIG
from .Messenger import messenger
from .utils import async_time_execution, get_headers, service_is_up

PRINT_SERVER_ADDRESS: str = CONFIG.printer.print_server_uri


async def print_image(file_path: Path, rfid_card_id: str, annotation: str | None = None) -> None:
    """print the provided image file"""
    if not CONFIG.printer.enable:
        logger.warning("Printer disabled, task dropped")
        return
    else:
        if not service_is_up(PRINT_SERVER_ADDRESS):
            message = "Printer is not available"
            messenger.error("Нет связи с сервером печати")
            raise ConnectionError(message)

    assert file_path.exists(), f"Image file {file_path} doesn't exist"
    assert file_path.is_file(), f"{file_path} is not an image file"
    task = print_image_task(file_path, rfid_card_id, annotation)

    if CONFIG.printer.skip_ack:
        logger.info(f"Printing task will be executed in the background ({CONFIG.printer.skip_ack=})")
        asyncio.create_task(task)
    else:
        await task


@async_time_execution
async def print_image_task(file_path: Path, rfid_card_id: str, annotation: str | None = None) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{PRINT_SERVER_ADDRESS}/print_image"
        headers: dict[str, str] = get_headers(rfid_card_id)
        data = {"annotation": annotation}
        files = {"image_file": open(file_path, "rb")}
        response: httpx.Response = await client.post(url=url, headers=headers, data=data, files=files)

    if response.is_error:
        raise httpx.RequestError(response.json().get("detail", ""))

    logger.info(f"Printed image '{file_path}'")
