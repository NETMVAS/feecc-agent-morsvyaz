import typing as tp

from pydantic import BaseModel


class NewUnitData(BaseModel):
    unit_type: str


class WorkbenchData(BaseModel):
    workbench_no: int


class WorkbenchStageDetails(WorkbenchData):
    production_stage_name: str


class WorkbenchExtraDetails(WorkbenchStageDetails):
    additional_info: tp.Dict[str, str]


class WorkbenchExtraDetailsWithoutStage(WorkbenchData):
    additional_info: tp.Dict[str, str]


class EmployeeDetails(WorkbenchData):
    employee_rfid_card_no: str


class BaseOut(BaseModel):
    status: bool
    comment: tp.Optional[str]


class UnitOut(BaseOut):
    unit_internal_id: tp.Optional[str]


class EmployeeData(BaseModel):
    name: str
    position: str


class EmployeeOut(BaseOut):
    employee_data: tp.Optional[EmployeeData]


class WorkbenchOut(WorkbenchData):
    state: int
    state_description: tp.Optional[str]
    employee_logged_in: bool
    employee: tp.Optional[EmployeeData]
    operation_ongoing: bool
    unit_internal_id: tp.Optional[str]
