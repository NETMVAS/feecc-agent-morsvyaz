import typing as tp

from pydantic import BaseModel


class GenericResponse(BaseModel):
    status_code: int
    detail: tp.Optional[str]


class WorkbenchData(BaseModel):
    workbench_no: int


class WorkbenchStageDetails(WorkbenchData):
    production_stage_name: str


class WorkbenchExtraDetails(WorkbenchStageDetails):
    additional_info: tp.Dict[str, str]


class WorkbenchExtraDetailsWithoutStage(WorkbenchData):
    additional_info: tp.Optional[tp.Dict[str, str]] = None


class EmployeeModel(BaseModel):
    name: str
    position: str


class EmployeeWCardModel(EmployeeModel):
    rfid_card_id: tp.Optional[str]


class WorkbenchOut(WorkbenchData):
    state: str
    state_description: tp.Optional[str]
    employee_logged_in: bool
    employee: tp.Optional[EmployeeModel]
    operation_ongoing: bool
    unit_internal_id: tp.Optional[str]
    unit_biography: tp.Optional[tp.List[str]]


class EmployeeOut(GenericResponse):
    employee_data: tp.Optional[EmployeeWCardModel]


class EmployeeID(BaseModel):
    employee_rfid_card_no: str


class UnitIn(BaseModel):
    unit_type: str


class UnitOut(GenericResponse):
    unit_internal_id: tp.Optional[str]


class UnitInfo(UnitOut):
    unit_biography: tp.List[str]


class ClientInfo(GenericResponse, WorkbenchData):
    pass
