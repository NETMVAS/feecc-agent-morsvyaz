import datetime as dt
import os
import re
import socket
import sys
from pathlib import Path
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


def service_is_up(service_endpoint: str | URL) -> bool:  # noqa: CAC001
    """Check if the provided host is reachable"""
    if isinstance(service_endpoint, str):
        service_endpoint = URL(service_endpoint)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            result = sock.connect_ex((service_endpoint.host, service_endpoint.port))
        except Exception as e:
            logger.debug(f"An error occured during socket connection attempt: {e}")
            result = 1

    return result == 0


def check_service_connectivity() -> None:  # noqa: CAC001,CCR001
    """check if all requsted external services are reachable"""
    services = (
        (CONFIG.ipfs_gateway.enable, CONFIG.ipfs_gateway.ipfs_server_uri),
    )
    failed_cnt, checked_cnt = 0, 0

    for _, service_endpoint in filter(lambda s: s[0], services):
        logger.info(f"Checking connection for service endpoint {service_endpoint}")
        checked_cnt += 1

        try:
            result = service_is_up(service_endpoint)
        except Exception as e:
            logger.debug(f"An error occured during socket connection attempt: {e}")
            result = False

        if result:
            logger.info(f"{service_endpoint} connection tested positive")
        else:
            logger.error(f"{service_endpoint} connection has been refused.")
            failed_cnt += 1

    if failed_cnt:
        logger.critical(f"{failed_cnt}/{checked_cnt} connectivity checks have failed. Exiting.")
        sys.exit(1)

    if checked_cnt:
        logger.info(f"{checked_cnt - failed_cnt}/{checked_cnt} service connectivity checks passed")


def export_version() -> None:
    """Parse app version and export it into environment variables at runtime"""
    version_file = Path("version.txt")
    if version_file.exists():
        with version_file.open("r") as f:
            version = f.read()
            os.environ["VERSION"] = version.strip("\n")
