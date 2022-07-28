from typing import Any

from .metrics import Metrics


class TrackedException(Exception):
    _labels: dict[str, str] = {}

    def __init__(self, *args: Any) -> None:
        Metrics().register(
            name=self.__class__.__name__,
            description=self.__class__.__doc__,
            labels=self._labels,
        )
        super().__init__(*args)


class UnitNotFoundError(TrackedException):
    """An error raised when no unit can be found with the provided key"""

    pass


class EmployeeNotFoundError(TrackedException):
    """An error raised when no employee can be found with the provided key"""

    pass


class StateForbiddenError(TrackedException):
    """Raised when state transition is forbidden"""

    pass
