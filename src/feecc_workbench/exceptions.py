from copy import copy
from typing import Any

from .metrics import Metrics


class TrackedException(Exception):  # noqa: N818
    """An exception that increments Prometheus metric counter for itself"""

    _labels: dict[str, str] = {}

    def __init__(self, *args: Any) -> None:
        labels = copy(self._labels)
        if args:
            labels["message"] = args[0]
        Metrics().register(
            name=self.__class__.__name__,
            description=self.__class__.__doc__,
            labels=labels,
        )
        super().__init__(*args)


class UnitNotFoundError(TrackedException):
    """An error raised when no unit can be found with the provided key"""


class EmployeeNotFoundError(TrackedException):
    """An error raised when no employee can be found with the provided key"""


class StateForbiddenError(TrackedException):
    """Raised when state transition is forbidden"""


class RobonomicsError(TrackedException):
    """Raised when Robonmics transactions fail"""
