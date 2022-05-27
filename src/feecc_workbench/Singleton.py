from __future__ import annotations

from typing import Any

from loguru import logger


class SingletonMeta(type):
    """
    The Singleton class ensures there is always only one instance of a certain class that  is globally available.
    This implementation is __init__ signature agnostic.
    """

    _instances: dict[Any, Any] = {}

    def __call__(cls: SingletonMeta, *args: Any, **kwargs: Any) -> Any:
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
            logger.info(f"Initialized a new instance of {cls.__name__} at {id(cls._instances[cls])}")
        return cls._instances[cls]
