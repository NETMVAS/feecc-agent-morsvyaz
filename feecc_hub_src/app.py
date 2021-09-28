import typing as tp
from dataclasses import asdict

import uvicorn
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from dependencies import get_employee_by_card_id, get_unit_by_internal_id, validate_sender
from feecc_hub import models as m
from feecc_hub.Config import Config
from feecc_hub.Unit import Unit
from feecc_hub.WorkBench import WorkBench
from feecc_hub.database import MongoDbWrapper

if tp.TYPE_CHECKING:
    from feecc_hub.Employee import Employee

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

# global variables
api = FastAPI(dependencies=[Depends(validate_sender)])

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.on_event("startup")
def startup_event() -> None:
    config = Config()
    MongoDbWrapper(config.global_config["mongo_db"]["mongo_connection_url"])
    WorkBench()


@api.post("/api/unit/new", response_model=tp.Union[m.UnitOut, m.GenericResponse])  # type: ignore
async def create_unit(payload: m.NewUnitData) -> tp.Union[m.UnitOut, m.GenericResponse]:
    """handle new Unit creation"""
    try:
        new_unit_internal_id: str = await WorkBench().create_new_unit(payload.unit_type)
        logger.info(f"Initialized new unit with internal ID {new_unit_internal_id}")
        return m.UnitOut(
            status=status.HTTP_200_OK,
            details="New unit created successfully",
            unit_internal_id=new_unit_internal_id,
        )

    except Exception as e:
        logger.error(f"Exception occurred while creating new Unit: {e}")
        return m.GenericResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR, details=str(e))


@api.post("/api/unit/{unit_internal_id}/start", response_model=m.GenericResponse)
async def unit_start_record(
    workbench_details: m.WorkbenchExtraDetails, unit: Unit = Depends(get_unit_by_internal_id)
) -> m.GenericResponse:
    """handle start recording operation on a Unit"""

    try:
        workbench: WorkBench = WorkBench()
        workbench.state.start_operation(
            unit, workbench_details.production_stage_name, workbench_details.additional_info
        )
        message: str = f"Started operation '{workbench_details.production_stage_name}' on Unit {unit.internal_id}"
        logger.info(message)
        return m.GenericResponse(status=status.HTTP_200_OK, details=message)

    except Exception as e:
        message = f"Couldn't handle request. An error occurred: {e}"
        logger.error(message)
        return m.GenericResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR, details=message)


@api.post("/api/unit/{unit_internal_id}/end", response_model=m.GenericResponse)
def unit_stop_record(
    workbench_data: m.WorkbenchExtraDetailsWithoutStage, unit: Unit = Depends(get_unit_by_internal_id)
) -> m.GenericResponse:
    """handle end recording operation on a Unit"""
    try:
        workbench: WorkBench = WorkBench()
        workbench.state.end_operation(unit.internal_id, workbench_data.additional_info)
        message: str = f"Ended current operation on unit {unit.internal_id}"
        logger.info(message)
        return m.GenericResponse(status=status.HTTP_200_OK, details=message)

    except Exception as e:
        message = f"Couldn't handle end record request. An error occurred: {e}"
        logger.error(message)
        return m.GenericResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR, details=message)


@api.post("/api/unit/{unit_internal_id}/upload", response_model=m.GenericResponse)
async def unit_upload_record(unit: Unit = Depends(get_unit_by_internal_id)) -> m.GenericResponse:
    """handle Unit lifecycle end"""
    try:
        unit.upload(MongoDbWrapper())
        return m.GenericResponse(status=status.HTTP_200_OK, details=f"Uploaded data for unit {unit.internal_id}")

    except Exception as e:
        message: str = f"Can't handle unit upload. An error occurred: {e}"
        logger.error(message)
        return m.GenericResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR, details=message)


@api.post("/api/employee/info", response_model=m.EmployeeOut)
def get_employee_data(employee: Employee = Depends(get_employee_by_card_id)) -> m.EmployeeOut:
    """return data for an Employee with matching ID card"""
    return m.EmployeeOut(
        status=status.HTTP_200_OK, details="Employee retrieved successfully", employee_data=asdict(employee)
    )


@api.post("/api/employee/log-in", response_model=m.EmployeeOut)
def log_in_employee(employee: Employee = Depends(get_employee_by_card_id)) -> m.EmployeeOut:
    """handle logging in the Employee at a given Workbench"""
    WorkBench().authorize_employee(employee.rfid_card_id)

    return m.EmployeeOut(
        status=status.HTTP_200_OK, details="Employee logged in successfully", employee_data=asdict(employee)
    )


@api.post("/api/employee/log-out", response_model=m.GenericResponse)
def log_out_employee() -> m.GenericResponse:
    """handle logging out the Employee at a given Workbench"""
    try:
        workbench: WorkBench = WorkBench()
        workbench.state.end_shift()
        if workbench.employee is not None:
            raise ValueError("Unable to logout employee")
        return m.GenericResponse(status=status.HTTP_200_OK, details="Employee logged out successfully")

    except Exception as e:
        message: str = f"An error occurred while logging out the Employee: {e}"
        logger.error(message)
        return m.GenericResponse(status=status.HTTP_500_INTERNAL_SERVER_ERROR, details=message)


@api.get("/api/unit/{unit_internal_id}/info", response_model=m.UnitInfo)
def get_unit_data(unit: Unit = Depends(get_unit_by_internal_id)) -> m.UnitInfo:
    """return data for a Unit with matching ID"""
    return m.UnitInfo(
        status=status.HTTP_200_OK,
        details="Unit data retrieved successfully",
        unit_internal_id=unit.internal_id,
        unit_biography={id_: {"stage": stage.name} for id_, stage in enumerate(unit.unit_biography)},
    )


@api.get("/api/workbench/status", response_model=m.WorkbenchOut)
def get_workbench_status() -> m.WorkbenchOut:
    """handle providing status of the given Workbench"""
    workbench: WorkBench = WorkBench()
    return m.WorkbenchOut(
        workbench_no=workbench.number,
        state=workbench.state_name,
        state_description=workbench.state_description,
        employee_logged_in=bool(workbench.employee),
        employee=workbench.employee.data if workbench.employee else None,
        operation_ongoing=workbench.is_operation_ongoing,
        unit_internal_id=workbench.unit_in_operation,
        unit_biography={
            id_: {"stage": stage.name} for id_, stage in enumerate(workbench.associated_unit.unit_biography)
        }
        if workbench.associated_unit
        else None,
    )


@api.get("/api/status/client_info", response_model=m.ClientInfo)
def get_client_info() -> m.ClientInfo:
    """A client can make a request to this endpoint to know if it's ip is recognized as a workbench and get the
    workbench number if that is the case"""
    workbench = WorkBench()
    return m.ClientInfo(
        status=status.HTTP_200_OK,
        details=f"Requested ip address is known as workbench no. {workbench.number}",
        workbench_no=workbench.number,
    )


if __name__ == "__main__":
    # start the server
    host: str = Config().global_config["api_server"]["ip"]
    port: int = Config().global_config["api_server"]["port"]
    uvicorn.run("app:api", host=host, port=port)
