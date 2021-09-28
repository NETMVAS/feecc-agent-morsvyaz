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
    additional_info: tp.Optional[tp.Dict[str, str]] = None


class EmployeeDetails(WorkbenchData):
    employee_rfid_card_no: str


class GenericResponse(BaseModel):
    status: int
    details: tp.Optional[str]


class UnitOut(GenericResponse):
    unit_internal_id: tp.Optional[str]


class UnitInfo(UnitOut):
    unit_biography: tp.Dict[int, tp.Dict[str, str]]


class EmployeeData(BaseModel):
    name: str
    position: str


class ClientInfo(GenericResponse):
    workbench_no: int


class EmployeeOut(GenericResponse):
    employee_data: tp.Optional[EmployeeData]


class WorkbenchOut(WorkbenchData):
    state: str
    state_description: tp.Optional[str]
    employee_logged_in: bool
    employee: tp.Optional[EmployeeData]
    operation_ongoing: bool
    unit_internal_id: tp.Optional[str]
    unit_biography: tp.Optional[tp.Dict[int, tp.Dict[str, str]]]
