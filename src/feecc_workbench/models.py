from time import time
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .states import State


class GenericResponse(BaseModel):
    status_code: int
    detail: str | None


class WorkbenchExtraDetails(BaseModel):
    additional_info: dict[str, str]


class WorkbenchExtraDetailsWithoutStage(BaseModel):
    additional_info: dict[str, str] | None = None
    premature_ending: bool = False


class EmployeeModel(BaseModel):
    name: str
    position: str


class EmployeeWCardModel(EmployeeModel):
    rfid_card_id: str | None


class WorkbenchOut(BaseModel):
    state: State
    employee_logged_in: bool
    employee: EmployeeModel | None
    operation_ongoing: bool
    unit_internal_id: str | None
    unit_status: str | None
    unit_biography: list[str] | None
    unit_components: dict[str, str | None] | None


class EmployeeOut(GenericResponse):
    employee_data: EmployeeWCardModel | None


class EmployeeID(BaseModel):
    employee_rfid_card_no: str


class UnitOut(GenericResponse):
    unit_internal_id: str | None


class UnitOutPendingEntry(BaseModel):
    unit_internal_id: str
    unit_name: str


class UnitOutPending(GenericResponse):
    units: list[UnitOutPendingEntry]


class BiographyStage(BaseModel):
    stage_name: str
    stage_schema_entry_id: str


class UnitInfo(UnitOut):
    unit_status: str
    unit_biography_completed: list[BiographyStage]
    unit_biography_pending: list[BiographyStage]
    unit_components: list[str] | None = None
    schema_id: str


class HidEvent(BaseModel):
    string: str
    name: str
    timestamp: float = Field(default_factory=time)
    info: dict[str, int | str] = {}


class ProductionSchemaStage(BaseModel):
    name: str
    stage_id: str
    type: str | None = None  # noqa: A003
    description: str | None = None
    equipment: list[str] | None = None
    workplace: str | None = None
    duration_seconds: int | None = None


class ProductionSchema(BaseModel):
    schema_id: str = Field(default_factory=lambda: uuid4().hex)
    unit_name: str
    unit_short_name: str | None = None
    production_stages: list[ProductionSchemaStage] | None = None
    required_components_schema_ids: list[str] | None = None
    parent_schema_id: str | None = None
    schema_type: str | None = None

    @property
    def is_composite(self) -> bool:
        return self.required_components_schema_ids is not None

    @property
    def is_a_component(self) -> bool:
        return self.parent_schema_id is not None

    @property
    def print_name(self) -> str:
        if self.unit_short_name is None:
            return self.unit_name
        return self.unit_short_name


class ProductionSchemaResponse(GenericResponse):
    production_schema: ProductionSchema


class SchemaListEntry(BaseModel):
    schema_id: str
    schema_name: str
    included_schemas: list[dict[str, Any]] | None


class SchemasList(GenericResponse):
    available_schemas: list[SchemaListEntry]
