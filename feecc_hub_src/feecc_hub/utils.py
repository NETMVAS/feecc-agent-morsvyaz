import re
import typing as tp
from functools import lru_cache
from time import time

from loguru import logger

from .config import config


def time_execution(func: tp.Any) -> tp.Any:
    """This decorator shows the execution time of the function object passed"""

    def wrap_func(*args: tp.Any, **kwargs: tp.Any) -> tp.Any:
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        logger.debug(f"Function {func.__name__!r} executed in {(t2 - t1):.4f}s")
        return result

    return wrap_func


def get_headers(rfid_card_id: str) -> tp.Dict[str, str]:
    """return a dict with all the headers required for using the backend"""
    return {"rfid-card-id": rfid_card_id}


@lru_cache
def identify_sender(sender_device_name: str) -> tp.Optional[str]:
    """identify, which device the input is coming from and if it is known return it's role"""
    known_hid_devices: tp.Dict[str, str] = config.known_hid_devices.dict()

    for sender_name, device_name in known_hid_devices.items():
        if device_name == sender_device_name:
            return sender_name

    return None


def is_a_ean13_barcode(string: str) -> bool:
    """define if the barcode scanner input is a valid EAN13 barcode"""
    return bool(re.fullmatch("\d{13}", string))
