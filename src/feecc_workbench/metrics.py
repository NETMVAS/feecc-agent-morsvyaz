from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from aioprometheus.collectors import Summary

from .Employee import Employee
from .Singleton import SingletonMeta
from .utils import export_version

if TYPE_CHECKING:
    from .Unit import Unit


class Metrics(metaclass=SingletonMeta):
    def __init__(self) -> None:
        self._metrics: dict[str, Summary] = {}
        export_version()
        app_version = Summary(name="app_version", doc="Runtime application version")
        app_version.observe(labels={"app_version": os.getenv("VERSION", "Unknown")}, value=1)

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

    def register_log_in(self, employee: Employee | None) -> None:
        """Register log_in event"""
        labels = {
            "event_type": "log_in",
            "employee_name": employee.name if employee else "Unknown",
        }
        self.register(name="production_metrics", description=None, labels=labels)

    def register_log_out(self, employee: Employee | None) -> None:
        """Register log_out event"""
        labels = {
            "event_type": "log_out",
            "employee_name": employee.name if employee else "Unknown",
        }
        self.register(name="production_metrics", description=None, labels=labels)

    def register_create_unit(self, employee: Employee | None, unit: Unit) -> None:
        """Register create_unit event"""
        labels = {
            "event_type": "create_unit",
            "employee_name": employee.name if employee else "Unknown",
            "unit_id": unit.internal_id,
            "unit_type": unit.schema.unit_name,
        }
        self.register(name="production_metrics", description=None, labels=labels)

    def register_complete_unit(self, employee: Employee | None, unit: Unit) -> None:
        """Register complete_unit event"""
        labels = {
            "event_type": "complete_unit",
            "employee_name": employee.name if employee else "Unknown",
            "unit_id": unit.internal_id,
            "unit_type": unit.schema.unit_name,
        }
        self.register(name="production_metrics", description=None, labels=labels)

    def register_complete_operation(self, employee: Employee | None, unit: Unit) -> None:
        """Register complete_operation event"""
        labels = {
            "event_type": "complete_operation",
            "employee_name": employee.name if employee else "Unknown",
            "unit_id": unit.internal_id,
            "unit_type": unit.schema.unit_name,
        }
        self.register(name="production_metrics", description=None, labels=labels)

    def register_generate_passport(self, employee: Employee | None, unit: Unit) -> None:
        """Register generate_passport event"""
        labels = {
            "event_type": "generate_passport",
            "employee_name": employee.name if employee else "Unknown",
            "unit_id": unit.internal_id,
            "unit_type": unit.schema.unit_name,
        }
        self.register(name="production_metrics", description=None, labels=labels)


metrics = Metrics()
