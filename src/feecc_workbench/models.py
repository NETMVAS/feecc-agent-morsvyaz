import typing as tp
from uuid import uuid4

from pydantic import BaseModel


class GenericResponse(BaseModel):
    status_code: int
    detail: tp.Optional[str]


class WorkbenchStageDetails(BaseModel):
    production_stage_name: str


class WorkbenchExtraDetails(WorkbenchStageDetails):
    additional_info: tp.Dict[str, str]


class WorkbenchExtraDetailsWithoutStage(BaseModel):
    additional_info: tp.Optional[tp.Dict[str, str]] = None


class EmployeeModel(BaseModel):
    name: str
    position: str


class EmployeeWCardModel(EmployeeModel):
    rfid_card_id: tp.Optional[str]


class WorkbenchOut(BaseModel):
    state: str
    state_description: tp.Optional[str]
    employee_logged_in: bool
    employee: tp.Optional[EmployeeModel]
    operation_ongoing: bool
    unit_internal_id: tp.Optional[str]
    unit_biography: tp.Optional[tp.List[str]]
    unit_components: tp.Optional[tp.Dict[str, tp.Optional[str]]]


class EmployeeOut(GenericResponse):
    employee_data: tp.Optional[EmployeeWCardModel]


class EmployeeID(BaseModel):
    employee_rfid_card_no: str


class UnitIn(BaseModel):
    unit_type: str
    component_names: tp.Optional[tp.List[str]] = None


class UnitOut(GenericResponse):
    unit_internal_id: tp.Optional[str]


class UnitInfo(UnitOut):
    unit_biography: tp.List[str]
    unit_components: tp.Optional[tp.List[str]] = None


class HidEvent(BaseModel):
    string: str
    name: str
    timestamp: float
    info: tp.Dict[str, tp.Union[int, str]]


class ProductionSchemaStage(BaseModel):
    name: str
    type: tp.Optional[str] = None
    description: tp.Optional[str] = None
    equipment: tp.Optional[tp.List[str]] = None
    workplace: tp.Optional[str] = None
    duration_seconds: tp.Optional[int] = None


class ProductionSchema(BaseModel):
    schema_id: str = uuid4().hex
    unit_name: str
    production_stages: tp.Optional[tp.List[ProductionSchemaStage]]
    required_components_schema_ids: tp.Optional[tp.List[str]] = None


class SchemaListEntry(BaseModel):
    schema_id: str
    schema_name: str


class SchemasList(GenericResponse):
    available_schemas: tp.List[SchemaListEntry]
