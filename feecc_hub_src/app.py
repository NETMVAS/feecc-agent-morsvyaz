import typing as tp

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from feecc_hub.exceptions import (
    EmployeeNotFoundError,
    EmployeeUnauthorizedError,
    WorkbenchNotFoundError,
)
from feecc_hub.Hub import Hub
from feecc_hub.models import (
    BaseOut,
    EmployeeData,
    EmployeeDetails,
    EmployeeOut,
    NewUnitData,
    UnitOut,
    WorkbenchData,
    WorkbenchExtraDetails,
    WorkbenchExtraDetailsWithoutStage,
)
from feecc_hub.Types import RequestPayload
from feecc_hub.Unit import Unit
from feecc_hub.WorkBench import WorkBench
from loguru import logger

from ._logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG

if tp.TYPE_CHECKING:
    from feecc_hub.Employee import Employee

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

# global variables
hub = Hub()
api = FastAPI()

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API request handlers


@api.post("/api/unit/new", response_model=UnitOut)
def create_unit(payload: NewUnitData) -> RequestPayload:
    """handle new Unit creation"""
    logger.debug(f"Got request at /api/unit/new with payload: {payload.dict()}")
    global hub

    try:
        new_unit_internal_id: str = hub.create_new_unit(payload.unit_type)
        response = UnitOut(
            status=True,
            comment="New unit created successfully",
            unit_internal_id=new_unit_internal_id,
        )
        logger.info(f"Initialized new unit with internal ID {new_unit_internal_id}")
        return dict(response.dict())

    except Exception as E:
        logger.error(f"Exception occurred while creating new Unit: {E}")
        response = UnitOut(
            status=False, comment=f"Could not create a new Unit. Internal error occurred: {E}"
        )
        return dict(response.dict())


@api.post("/api/unit/{unit_internal_id}/start", response_model=BaseOut)
def unit_start_record(
    workbench_details: WorkbenchExtraDetails, unit_internal_id: str
) -> RequestPayload:
    """handle start recording operation on a Unit"""
    global hub
    request_payload: RequestPayload = workbench_details.dict()

    logger.debug(
        f"Got request at /api/unit/{unit_internal_id}/start with payload:" f" {request_payload}"
    )

    try:
        workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
        unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)
        workbench.state.start_operation(
            unit, request_payload["production_stage_name"], request_payload["additional_info"]
        )
        message = (
            f"Started operation '{request_payload['production_stage_name']}' on Unit {unit_internal_id} at "
            f"Workbench no. {request_payload['workbench_no']} "
        )
        response_data = {"status": True, "comment": message}
        logger.info(message)
        return response_data

    except Exception as E:
        message = f"Couldn't handle request. An error occurred: {E}"
        logger.error(message)
        logger.debug(request_payload)
        response_data = {"status": False, "comment": message}
        return response_data


@api.post("/api/unit/{unit_internal_id}/end", response_model=BaseOut)
def unit_stop_record(
    workbench_data: WorkbenchExtraDetailsWithoutStage, unit_internal_id: str
) -> RequestPayload:
    """handle end recording operation on a Unit"""
    global hub
    request_payload = workbench_data.dict()

    logger.debug(
        f"Got request at /api/unit/{unit_internal_id}/end with payload:" f" {request_payload}"
    )

    try:
        workbench_no: int = request_payload["workbench_no"]
        additional_info: tp.Optional[RequestPayload] = request_payload["additional_info"] or None
        workbench: WorkBench = hub.get_workbench_by_number(workbench_no)
        workbench.state.end_operation(unit_internal_id, additional_info)
        message = f"Ended current operation on unit {unit_internal_id} (workbench {workbench_no})"
        return {"status": True, "comment": message}

    except Exception as e:
        logger.error(f"Couldn't handle end record request. An error occurred: {e}")
        return {"status": False, "comment": "Couldn't handle end record request."}


@api.post("/api/unit/{unit_internal_id}/upload", response_model=BaseOut)
def unit_upload_record(workbench: WorkbenchData, unit_internal_id: str) -> RequestPayload:
    """handle Unit lifecycle end"""
    global hub
    request_payload = workbench.dict()

    logger.debug(
        f"Got request at /api/unit/{unit_internal_id}/upload with payload:" f" {request_payload}"
    )

    try:
        unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)
        unit.upload()

        return {"status": True, "comment": f"Uploaded data for unit {unit_internal_id}"}

    except Exception as e:
        error_message = f"Can't handle unit upload. An error occurred: {e}"
        logger.error(error_message)

    return {"status": False, "comment": error_message}


@api.post("/api/employee/{rfid_card_id}/info", response_model=EmployeeOut)
def get_employee_data(rfid_card_id: str) -> RequestPayload:
    """return data for an Employee with matching ID card"""
    logger.debug(f"Got request at /api/employee/{rfid_card_id}/info")

    try:
        employee: Employee = hub.get_employee_by_card_id(rfid_card_id)
        response_data = {
            "status": True,
            "comment": "Employee retrieved successfully",
            "employee_data": EmployeeData(**employee.data).dict(),
        }
        return response_data

    except EmployeeNotFoundError as E:
        message = f"Employee not found: {E}"
        logger.error(message)
        response_data = {"status": False, "comment": message}
        return response_data

    except Exception as e:
        message = f"An unknown error occurred while fetching Employee data: {e}"
        logger.error(message)
        response_data = {"status": False, "comment": message}
        return response_data


@api.post("/api/employee/log-in", response_model=EmployeeOut)
def log_in_employee(employee_data: EmployeeDetails) -> RequestPayload:
    """handle logging in the Employee at a given Workbench"""
    global hub
    request_payload = employee_data.dict()

    logger.debug(f"Got request at /api/employee/log-in with payload:" f" {request_payload}")

    try:
        workbench_no: int = int(request_payload["workbench_no"])
        employee_rfid_card_no: str = request_payload["employee_rfid_card_no"]
        workbench: WorkBench = hub.get_workbench_by_number(workbench_no)

        hub.authorize_employee(employee_rfid_card_no, workbench_no)
        employee: tp.Optional[Employee] = workbench.employee

        if employee is None:
            raise EmployeeUnauthorizedError

        response_data = {
            "status": True,
            "comment": "Employee logged in successfully",
            "employee_data": EmployeeData(**employee.data).dict(),
        }

        return response_data

    except WorkbenchNotFoundError as E:
        message = f"Could not log in the Employee. Workbench not found: {E}"
        logger.error(message)
        response_data = {"status": False, "comment": message}
        return response_data

    except EmployeeNotFoundError as E:
        message = f"Could not log in the Employee. Employee not found: {E}"
        logger.error(message)
        response_data = {"status": False, "comment": message}
        return response_data

    except Exception as e:
        message = f"An error occurred while logging in the Employee: {e}"
        logger.error(message)
        response_data = {"status": False, "comment": message}
        return response_data


@api.post("/api/employee/log-out")
def log_out_employee(employee: WorkbenchData) -> RequestPayload:
    """handle logging out the Employee at a given Workbench"""
    global hub
    request_payload = employee.dict()

    logger.debug(f"Got request at /api/employee/log-out with payload:" f" {request_payload}")

    try:
        workbench: WorkBench = hub.get_workbench_by_number(int(request_payload["workbench_no"]))
        workbench.state.end_shift()

        if workbench.employee is None:
            response_data = {
                "status": True,
                "comment": "Employee logged out successfully",
            }

            return response_data

        else:
            raise ValueError("Unable to logout employee")

    except Exception as e:
        message = f"An error occurred while logging out the Employee: {e}"
        logger.error(message)

        response_data = {"status": False, "comment": message}

        return response_data


@api.get("/api/workbench/{workbench_no}/status")
def get_workbench_status(workbench_no: int) -> RequestPayload:
    """handle providing status of the given Workbench"""
    # find the WorkBench with the provided number

    try:
        workbench: WorkBench = hub.get_workbench_by_number(workbench_no)
    except Exception as E:
        return {"status": False, "comment": str(E)}

    employee: tp.Optional[Employee] = workbench.employee
    employee_data: tp.Optional[tp.Dict[str, str]] = employee.data if employee else None

    workbench_status_dict: RequestPayload = {
        "workbench_no": workbench.number,
        "state": workbench.state_name,
        "state_description": workbench.state_description,
        "employee_logged_in": bool(employee),
        "employee": employee_data,
        "operation_ongoing": workbench.is_operation_ongoing,
        "unit_internal_id": workbench.unit_in_operation,
        "unit_biography": None,
    }

    if workbench_status_dict["operation_ongoing"]:
        workbench_status_dict["unit_biography"] = {
            id_: {"stage": stage.name}
            for id_, stage in enumerate(workbench.associated_unit.unit_biography)
        }

    return workbench_status_dict


if __name__ == "__main__":
    # start the server
    host: str = hub.config["api_server"]["ip"]
    port: int = hub.config["api_server"]["port"]
    uvicorn.run("app:api", host=host, port=port)
