import typing as tp
from time import time

from loguru import logger


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
    return {"rfid_card_id": rfid_card_id}
