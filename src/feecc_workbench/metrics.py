import os
import re

from aioprometheus.collectors import Summary

from .Singleton import SingletonMeta

app_version = Summary(name="app_version", doc="Runtime application version")
app_version.observe(labels={"app_version": os.getenv("VERSION", "Unknown")}, value=1)


class Metrics(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._metrics: dict[str, Summary] = {}

    @staticmethod
    def _transform(text: str) -> str:
        """Convert camel/pascal case to snake_case"""
        return re.sub(r"(?<!^)(?=[A-Z])", "_", text).lower()

    def _create(self, name: str, description: str) -> None:
        """Create metric"""
        self._metrics[name] = Summary(name=self._transform(name), doc=description)

    def register(self, name: str, description: str | None, labels: dict[str, str] | None = None) -> None:
        """Register metric event"""
        if labels is None:
            labels = {}
        if name not in self._metrics:
            self._create(name=name, description=description or "")
        self._metrics[name].observe(labels=labels, value=1)
