import datetime as dt
import re
from time import time
from typing import Any

from loguru import logger

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
