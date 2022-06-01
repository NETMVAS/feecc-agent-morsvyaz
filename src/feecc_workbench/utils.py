import datetime as dt
import re
import socket
import sys
from time import time
from typing import Any

from loguru import logger
from yarl import URL

from .config import CONFIG

TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M:%S"


def time_execution(func: Any) -> Any:
    """This decorator shows the execution time of the function object passed"""

    def wrap_func(*args: Any, **kwargs: Any) -> Any:
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        logger.debug(f"Function {func.__name__!r} executed in {(t2 - t1):.4f}s")
        return result

    return wrap_func


def async_time_execution(func: Any) -> Any:
    """This decorator shows the execution time of the function object passed"""

    async def wrap_func(*args: Any, **kwargs: Any) -> Any:
        t1 = time()
        result = await func(*args, **kwargs)
        t2 = time()
        logger.debug(f"Function {func.__name__!r} executed in {(t2 - t1):.4f}s")
        return result

    return wrap_func


def get_headers(rfid_card_id: str) -> dict[str, str]:
    """return a dict with all the headers required for using the backend"""
    return {"rfid-card-id": rfid_card_id}


def is_a_ean13_barcode(string: str) -> bool:
    """define if the barcode scanner input is a valid EAN13 barcode"""
    return bool(re.fullmatch(r"\d{13}", string))


def timestamp() -> str:
    """generate formatted timestamp for the invocation moment"""
    return dt.datetime.now().strftime(TIMESTAMP_FORMAT)


def check_service_connectivity() -> None:
    """check if all requsted external services are reachable"""
    services = (
        (CONFIG.camera.enable, CONFIG.camera.cameraman_uri),
        (CONFIG.ipfs_gateway.enable, CONFIG.ipfs_gateway.ipfs_server_uri),
        (CONFIG.printer.enable, CONFIG.printer.print_server_uri),
    )
    failed_cnt = 0
    checked_cnt = 0

    for enabled, service_endpoint in services:
        if not enabled:
            continue

        logger.info(f"Checking connection for service endpoint {service_endpoint}")
        checked_cnt += 1
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        uri = URL(service_endpoint)
        result = sock.connect_ex((uri.host, uri.port))

        if result == 0:
            logger.info(f"{service_endpoint} connection tested positive")
        else:
            logger.error(f"{service_endpoint} connection has been refused.")
            failed_cnt += 1

    if failed_cnt:
        logger.critical(f"{failed_cnt}/{checked_cnt} connectivity checks have failed. Exiting.")
        sys.exit(1)

    if checked_cnt:
        logger.info(f"{checked_cnt - failed_cnt}/{checked_cnt} service connectivity checks passed")
