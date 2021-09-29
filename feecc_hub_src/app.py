import typing as tp

import uvicorn
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from dependencies import get_employee_by_card_id, get_unit_by_internal_id, validate_sender
from feecc_hub import models as mdl
from feecc_hub.Config import Config
from feecc_hub.Employee import Employee
from feecc_hub.Unit import Unit
from feecc_hub.WorkBench import WorkBench
from feecc_hub.database import MongoDbWrapper
from feecc_hub.exceptions import StateForbiddenError

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
    MongoDbWrapper()
    WorkBench()


@api.post("/api/unit/new", response_model=tp.Union[mdl.UnitOut, mdl.GenericResponse])  # type: ignore
async def create_unit(payload: mdl.UnitIn) -> tp.Union[mdl.UnitOut, mdl.GenericResponse]:
    """handle new Unit creation"""
    try:
        new_unit_internal_id: str = await WorkBench().create_new_unit(payload.unit_type)
        logger.info(f"Initialized new unit with internal ID {new_unit_internal_id}")
        return mdl.UnitOut(
            status_code=status.HTTP_200_OK,
            detail="New unit created successfully",
            unit_internal_id=new_unit_internal_id,
        )

    except Exception as e:
        logger.error(f"Exception occurred while creating new Unit: {e}")
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@api.get("/api/unit/{unit_internal_id}/info", response_model=mdl.UnitInfo)
def get_unit_data(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.UnitInfo:
    """return data for a Unit with matching ID"""
    return mdl.UnitInfo(
        status_code=status.HTTP_200_OK,
        detail="Unit data retrieved successfully",
        unit_internal_id=unit.internal_id,
        unit_biography=[stage.name for stage in unit.biography],
    )


@api.post("/api/unit/{unit_internal_id}/start", response_model=mdl.GenericResponse)
async def unit_start_record(
    workbench_details: mdl.WorkbenchExtraDetails, unit: Unit = Depends(get_unit_by_internal_id)
) -> mdl.GenericResponse:
    """handle start recording operation on a Unit"""
    try:
        workbench = WorkBench()
        workbench.state.start_operation(
            unit, workbench_details.production_stage_name, workbench_details.additional_info
        )
        message: str = f"Started operation '{workbench_details.production_stage_name}' on Unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/api/unit/{unit_internal_id}/end", response_model=mdl.GenericResponse)
def unit_stop_record(
    workbench_data: mdl.WorkbenchExtraDetailsWithoutStage, unit: Unit = Depends(get_unit_by_internal_id)
) -> mdl.GenericResponse:
    """handle end recording operation on a Unit"""
    try:
        workbench = WorkBench()
        workbench.state.end_operation(unit.internal_id, workbench_data.additional_info)
        message: str = f"Ended current operation on unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle end record request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/api/unit/{unit_internal_id}/upload", response_model=mdl.GenericResponse)
async def unit_upload_record(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.GenericResponse:
    """handle Unit lifecycle end"""
    try:
        unit.upload()
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=f"Uploaded data for unit {unit.internal_id}")

    except Exception as e:
        message: str = f"Can't handle unit upload. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/api/employee/info", response_model=mdl.EmployeeOut)
def get_employee_data(employee: Employee = Depends(get_employee_by_card_id)) -> mdl.EmployeeOut:
    """return data for an Employee with matching ID card"""
    return mdl.EmployeeOut(
        status_code=status.HTTP_200_OK, detail="Employee retrieved successfully", employee_data=employee
    )


@api.post("/api/employee/log-in", response_model=tp.Union[mdl.EmployeeOut, mdl.GenericResponse])
def log_in_employee(
    employee: Employee = Depends(get_employee_by_card_id),
) -> tp.Union[mdl.EmployeeOut, mdl.GenericResponse]:
    """handle logging in the Employee at a given Workbench"""
    try:
        WorkBench().state.start_shift(employee)
        return mdl.EmployeeOut(
            status_code=status.HTTP_200_OK, detail="Employee logged in successfully", employee_data=employee
        )

    except StateForbiddenError as e:
        return mdl.GenericResponse(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@api.post("/api/employee/log-out", response_model=mdl.GenericResponse)
def log_out_employee() -> mdl.GenericResponse:
    """handle logging out the Employee at a given Workbench"""
    try:
        workbench = WorkBench()
        workbench.state.end_shift()
        if workbench.employee is not None:
            raise ValueError("Unable to logout employee")
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Employee logged out successfully")

    except Exception as e:
        message: str = f"An error occurred while logging out the Employee: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.get("/api/workbench/status", response_model=mdl.WorkbenchOut)
def get_workbench_status() -> mdl.WorkbenchOut:
    """handle providing status of the given Workbench"""
    workbench = WorkBench()
    return mdl.WorkbenchOut(
        workbench_no=workbench.number,
        state=workbench.state_name,
        state_description=workbench.state_description,
        employee_logged_in=bool(workbench.employee),
        employee=workbench.employee.data if workbench.employee else None,
        operation_ongoing=workbench.is_operation_ongoing,
        unit_internal_id=workbench.unit_in_operation_id,
        unit_biography=[stage.name for stage in workbench.unit.biography] if workbench.unit else None,
    )


@api.get("/api/workbench/client_info", response_model=mdl.ClientInfo)
def get_client_info() -> mdl.ClientInfo:
    """A client can make a request to this endpoint to know if it's ip is recognized as a workbench and get the
    workbench number if that is the case"""
    workbench = WorkBench()
    return mdl.ClientInfo(
        status_code=status.HTTP_200_OK,
        detail=f"Requested ip address is known as workbench no. {workbench.number}",
        workbench_no=workbench.number,
    )


if __name__ == "__main__":
    host: str = Config().global_config["api_server"]["ip"]
    port: int = Config().global_config["api_server"]["port"]
    uvicorn.run("app:api", host=host, port=port)
