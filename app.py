import uvicorn
import atexit
import logging
import typing as tp

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from feecc_hub.Hub import Hub
from feecc_hub.Unit import Unit
from feecc_hub.WorkBench import WorkBench
from feecc_hub.exceptions import (
    WorkbenchNotFoundError,
    EmployeeNotFoundError,
    EmployeeUnauthorizedError,
)
from feecc_hub.models import (
    WorkbenchData,
    WorkbenchStageDetails,
    WorkbenchExtraDetails,
    EmployeeDetails,
    EmployeeData,
    BaseOut,
    UnitOut,
    EmployeeOut,
    WorkbenchOut,
)

if tp.TYPE_CHECKING:
    from feecc_hub.Employee import Employee

# set up logging
logging.basicConfig(
    level=logging.DEBUG, filename="hub.log", format="%(levelname)s (%(asctime)s): %(message)s"
)

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


@atexit.register
def end_session() -> None:
    """a function to execute when daemon exits"""
    logging.info("Sigterm registered. Handling.")
    global hub
    hub.end_session()
    logging.info("Sigterm handling success")


# REST API request handlers


@api.post("/api/unit/new", response_model=UnitOut)
def create_unit(workbench: WorkbenchData) -> tp.Dict[str, tp.Any]:
    """handle new Unit creation"""
    try:
        workbench_no: int = workbench.workbench_no
        logging.debug(f"Received a request to create a new Unit from workbench no. {workbench_no}")

    except Exception as E:
        logging.error(
            f"Can't handle the request. Request payload: {workbench.json()}. Exception occurred: {E}"
        )
        response = UnitOut(status=False, comment="Can't handle request", unit_internal_id="")
        return response.dict()  # type : ignore

    global hub

    try:
        new_unit_internal_id: str = hub.create_new_unit()
        response = UnitOut(
            status=True,
            comment="New unit created successfully",
            unit_internal_id=new_unit_internal_id,
        )
        logging.info(f"Initialized new unit with internal ID {new_unit_internal_id}")
        return response.dict()  # type : ignore

    except Exception as E:
        logging.error(f"Exception occurred while creating new Unit: {E}")
        response = UnitOut(
            status=False, comment=f"Could not create a new Unit. Internal error occurred: {E}"
        )
        return response.dict()


@api.post("/api/unit/{unit_internal_id}/start", response_model=BaseOut)
def unit_start_record(
    workbench_details: WorkbenchExtraDetails, unit_internal_id: str
) -> tp.Dict[str, tp.Any]:
    """handle start recording operation on a Unit"""
    global hub
    request_payload: tp.Dict[str, tp.Any] = workbench_details.dict()

    try:
        workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
        unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)
        workbench.start_operation(
            unit, request_payload["production_stage_name"], request_payload["additional_info"]
        )
        message = (
            f"Started operation '{request_payload['production_stage_name']}' on Unit {unit_internal_id} at "
            f"Workbench no. {request_payload['workbench_no']} "
        )
        response_data = {"status": True, "comment": message}
        logging.info(message)
        return response_data

    except Exception as E:
        message = f"Couldn't handle request. An error occurred: {E}"
        logging.error(message)
        logging.debug(request_payload)
        response_data = {"status": False, "comment": message}
        return response_data


@api.post("/api/unit/{unit_internal_id}/end", response_model=BaseOut)
def unit_stop_record(
    workbench_data: WorkbenchStageDetails, unit_internal_id: str
) -> tp.Dict[str, tp.Any]:
    """handle end recording operation on a Unit"""
    global hub
    request_payload = workbench_data.dict()

    logging.info(f"Received a request to end record for unit with int. id {unit_internal_id}")
    logging.debug(request_payload)

    try:
        workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
        workbench.end_operation(unit_internal_id)
        return {"status": True, "comment": "ok"}

    except Exception as e:
        logging.error(f"Couldn't handle end record request. An error occurred: {e}")
        return {"status": False, "comment": "Couldn't handle end record request."}


@api.post("/api/unit/{unit_internal_id}/upload", response_model=BaseOut)
def unit_upload_record(workbench: WorkbenchData, unit_internal_id: str) -> tp.Dict[str, tp.Any]:
    """handle Unit lifecycle end"""
    global hub
    request_payload = workbench.dict()

    logging.info(f"Received a request to upload unit with int. id {unit_internal_id}")
    logging.debug(request_payload)

    try:
        unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)
        unit.upload()

        return {"status": True, "comment": f"Uploaded data for unit {unit_internal_id}"}

    except Exception as e:
        error_message = f"Can't handle unit upload. An error occurred: {e}"
        logging.error(error_message)

    return {"status": False, "comment": error_message}


@api.post("/api/employee/log-in", response_model=EmployeeOut)
def log_in_employee(employee_data: EmployeeDetails) -> tp.Dict[str, tp.Any]:
    """handle logging in the Employee at a given Workbench"""
    global hub
    request_payload = employee_data.dict()

    logging.info("Handling logging in the employee")
    logging.debug(request_payload)

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
        logging.error(message)
        response_data = {"status": False, "comment": message}
        return response_data

    except EmployeeNotFoundError as E:
        message = f"Could not log in the Employee. Employee not found: {E}"
        logging.error(message)
        response_data = {"status": False, "comment": message}
        return response_data

    except Exception as e:
        message = f"An error occurred while logging in the Employee: {e}"
        logging.error(message)
        response_data = {"status": False, "comment": message}
        return response_data


@api.post(
    "/api/employee/log-out",
)
def log_out_employee(employee: EmployeeDetails) -> tp.Dict[str, tp.Any]:
    """handle logging out the Employee at a given Workbench"""
    global hub
    request_payload = employee.dict()

    logging.info("Handling logging out the employee")
    logging.debug(request_payload)

    try:
        workbench: WorkBench = hub.get_workbench_by_number(int(request_payload["workbench_no"]))
        workbench.end_shift()

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
        logging.error(message)

        response_data = {"status": False, "comment": message}

        return response_data


@api.get(
    "/api/workbench/<int:workbench_no>/status",
    response_model=WorkbenchOut,
    response_model_include={"status", "comment"},
)
def get(workbench_no: int) -> tp.Dict[str, tp.Union[str, bool]]:
    """handle providing status of the given Workbench"""
    # find the WorkBench with the provided number
    try:
        workbench: WorkBench = hub.get_workbench_by_number(workbench_no)
    except Exception as E:
        return {"status": False, "comment": str(E)}

    employee: tp.Optional[Employee] = workbench.employee
    employee_data: tp.Optional[tp.Dict[str, str]] = employee.data if employee else None

    workbench_status_dict: tp.Dict[str, tp.Any] = {
        "workbench_no": workbench.number,
        "state": workbench.state_number,
        "state_description": workbench.state_description,
        "employee_logged_in": bool(employee),
        "employee": employee_data,
        "operation_ongoing": workbench.is_operation_ongoing,
        "unit_internal_id": workbench.unit_in_operation,
    }

    return workbench_status_dict


if __name__ == "__main__":
    # start the server
    host: str = hub.config["api_server"]["ip"]
    port: int = hub.config["api_server"]["port"]
    uvicorn.run("app:api", host=host, port=port)
