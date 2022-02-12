import typing as tp
from time import time
from uuid import uuid4

from pydantic import BaseModel, Field

from .states import State


class GenericResponse(BaseModel):
    status_code: int
    detail: tp.Optional[str]


class WorkbenchExtraDetails(BaseModel):
    additional_info: tp.Dict[str, str]


class WorkbenchExtraDetailsWithoutStage(BaseModel):
    additional_info: tp.Optional[tp.Dict[str, str]] = None
    premature_ending: bool = False


class EmployeeModel(BaseModel):
    name: str
    position: str


class EmployeeWCardModel(EmployeeModel):
    rfid_card_id: tp.Optional[str]


class WorkbenchOut(BaseModel):
    state: State
    employee_logged_in: bool
    employee: tp.Optional[EmployeeModel]
    operation_ongoing: bool
    unit_internal_id: tp.Optional[str]
    unit_status: tp.Optional[str]
    unit_biography: tp.Optional[tp.List[str]]
    unit_components: tp.Optional[tp.Dict[str, tp.Optional[str]]]


class EmployeeOut(GenericResponse):
    employee_data: tp.Optional[EmployeeWCardModel]


class EmployeeID(BaseModel):
    employee_rfid_card_no: str


class UnitOut(GenericResponse):
    unit_internal_id: tp.Optional[str]


class UnitOutPendingEntry(BaseModel):
    unit_internal_id: str
    unit_name: str


class UnitOutPending(GenericResponse):
    units: tp.List[UnitOutPendingEntry]


class UnitInfo(UnitOut):
    unit_status: str
    unit_biography_completed: tp.List[str]
    unit_biography_pending: tp.List[str]
    unit_components: tp.Optional[tp.List[str]] = None
    schema_id: str


class HidEvent(BaseModel):
    string: str
    name: str
    timestamp: float = Field(default_factory=time)
    info: tp.Dict[str, tp.Union[int, str]] = {}


class ProductionSchemaStage(BaseModel):
    name: str
    type: tp.Optional[str] = None
    description: tp.Optional[str] = None
    equipment: tp.Optional[tp.List[str]] = None
    workplace: tp.Optional[str] = None
    duration_seconds: tp.Optional[int] = None


class ProductionSchema(BaseModel):
    schema_id: str = Field(default_factory=lambda: uuid4().hex)
    unit_name: str
    production_stages: tp.Optional[tp.List[ProductionSchemaStage]] = None
    required_components_schema_ids: tp.Optional[tp.List[str]] = None
    parent_schema_id: tp.Optional[str] = None
    schema_type: tp.Optional[str] = None

    @property
    def is_composite(self) -> bool:
        return self.required_components_schema_ids is not None

    @property
    def is_a_component(self) -> bool:
        return self.parent_schema_id is not None


class ProductionSchemaResponse(GenericResponse):
    production_schema: ProductionSchema


class SchemaListEntry(BaseModel):
    schema_id: str
    schema_name: str
    included_schemas: tp.Optional[tp.List[tp.Dict[str, tp.Any]]]


class SchemasList(GenericResponse):
    available_schemas: tp.List[SchemaListEntry]
