import typing as tp

import uvicorn
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from dependencies import get_employee_by_card_id, get_unit_by_internal_id, validate_sender
from feecc_hub import models as mdl, states, utils
from feecc_hub.Employee import Employee
from feecc_hub.Unit import Unit
from feecc_hub.WorkBench import WorkBench
from feecc_hub.config import config
from feecc_hub.database import MongoDbWrapper
from feecc_hub.exceptions import StateForbiddenError

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

# global variables
api = FastAPI(dependencies=[Depends(validate_sender)], title="Feecc Workbench daemon")

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKBENCH = WorkBench()


@api.on_event("startup")
def startup_event() -> None:
    MongoDbWrapper()


@api.post("/unit/new", response_model=tp.Union[mdl.UnitOut, mdl.GenericResponse], tags=["unit"])  # type: ignore
async def create_unit(payload: mdl.UnitIn) -> tp.Union[mdl.UnitOut, mdl.GenericResponse]:
    """handle new Unit creation"""
    try:
        unit: Unit = await WORKBENCH.create_new_unit(payload.unit_type)
        logger.info(f"Initialized new unit with internal ID {unit.internal_id}")
        return mdl.UnitOut(
            status_code=status.HTTP_200_OK,
            detail="New unit created successfully",
            unit_internal_id=unit.internal_id,
        )

    except Exception as e:
        logger.error(f"Exception occurred while creating new Unit: {e}")
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@api.get("/unit/{unit_internal_id}/info", response_model=mdl.UnitInfo, tags=["unit"])
def get_unit_data(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.UnitInfo:
    """return data for a Unit with matching ID"""
    return mdl.UnitInfo(
        status_code=status.HTTP_200_OK,
        detail="Unit data retrieved successfully",
        unit_internal_id=unit.internal_id,
        unit_biography=[stage.name for stage in unit.biography],
    )


@api.post("/unit/{unit_internal_id}/start", response_model=mdl.GenericResponse, tags=["unit"])
async def unit_start_record(
    workbench_details: mdl.WorkbenchExtraDetails, unit: Unit = Depends(get_unit_by_internal_id)
) -> mdl.GenericResponse:
    """handle start recording operation on a Unit"""
    try:
        workbench = WORKBENCH
        await workbench.start_operation(workbench_details.production_stage_name, workbench_details.additional_info)
        message: str = f"Started operation '{workbench_details.production_stage_name}' on Unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/unit/{unit_internal_id}/end", response_model=mdl.GenericResponse, tags=["unit"])
async def unit_stop_record(
    workbench_data: mdl.WorkbenchExtraDetailsWithoutStage, unit: Unit = Depends(get_unit_by_internal_id)
) -> mdl.GenericResponse:
    """handle end recording operation on a Unit"""
    try:
        await WORKBENCH.end_operation(workbench_data.additional_info)
        message: str = f"Ended current operation on unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle end record request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/unit/{unit_internal_id}/upload", response_model=mdl.GenericResponse, tags=["unit"])
async def unit_upload_record(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.GenericResponse:
    """handle Unit lifecycle end"""
    try:
        if WORKBENCH.employee is None:
            raise StateForbiddenError("Employee is not authorized on the workbench")

        await unit.upload(MongoDbWrapper(), WORKBENCH.employee.rfid_card_id)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=f"Uploaded data for unit {unit.internal_id}")

    except Exception as e:
        message: str = f"Can't handle unit upload. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/employee/info", response_model=mdl.EmployeeOut, tags=["employee"])
def get_employee_data(employee: mdl.EmployeeWCardModel = Depends(get_employee_by_card_id)) -> mdl.EmployeeOut:
    """return data for an Employee with matching ID card"""
    return mdl.EmployeeOut(
        status_code=status.HTTP_200_OK, detail="Employee retrieved successfully", employee_data=employee
    )


@api.post("/employee/log-in", response_model=tp.Union[mdl.EmployeeOut, mdl.GenericResponse], tags=["employee"])  # type: ignore
def log_in_employee(
    employee: mdl.EmployeeWCardModel = Depends(get_employee_by_card_id),
) -> tp.Union[mdl.EmployeeOut, mdl.GenericResponse]:
    """handle logging in the Employee at a given Workbench"""
    try:
        WORKBENCH.log_in(Employee(rfid_card_id=employee.rfid_card_id, name=employee.name, position=employee.position))
        return mdl.EmployeeOut(
            status_code=status.HTTP_200_OK, detail="Employee logged in successfully", employee_data=employee
        )

    except StateForbiddenError as e:
        return mdl.GenericResponse(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@api.post("/employee/log-out", response_model=mdl.GenericResponse, tags=["employee"])
def log_out_employee() -> mdl.GenericResponse:
    """handle logging out the Employee at a given Workbench"""
    try:
        WORKBENCH.log_out()
        if WORKBENCH.employee is not None:
            raise ValueError("Unable to logout employee")
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Employee logged out successfully")

    except Exception as e:
        message: str = f"An error occurred while logging out the Employee: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/workbench/assign-unit/{unit_internal_id}", response_model=mdl.GenericResponse, tags=["workbench"])
def assign_unit(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.GenericResponse:
    """assign the provided unit to the workbench"""
    try:
        WORKBENCH.assign_unit(unit)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=f"Unit {unit.internal_id} has been assigned")

    except Exception as e:
        message: str = f"An error occurred during unit assignment: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.post("/workbench/remove-unit", response_model=mdl.GenericResponse, tags=["workbench"])
def remove_unit() -> mdl.GenericResponse:
    """remove the unit from the workbench"""
    try:
        WORKBENCH.remove_unit()
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Unit has been removed")

    except Exception as e:
        message: str = f"An error occurred during unit removal: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@api.get("/workbench/status", response_model=mdl.WorkbenchOut, tags=["workbench"])
def get_workbench_status() -> mdl.WorkbenchOut:
    """handle providing status of the given Workbench"""
    return mdl.WorkbenchOut(
        workbench_no=WORKBENCH.number,
        state=WORKBENCH.state.name,
        state_description=WORKBENCH.state.description,
        employee_logged_in=bool(WORKBENCH.employee),
        employee=WORKBENCH.employee.data if WORKBENCH.employee else None,
        operation_ongoing=WORKBENCH.state is states.PRODUCTION_STAGE_ONGOING_STATE,
        unit_internal_id=WORKBENCH.unit.internal_id if WORKBENCH.unit else None,
        unit_biography=[stage.name for stage in WORKBENCH.unit.biography] if WORKBENCH.unit else None,
    )


@api.get("/workbench/client_info", response_model=mdl.ClientInfo, tags=["workbench"])
def get_client_info() -> mdl.ClientInfo:
    """A client can make a request to this endpoint to know if it's ip is recognized as a workbench and get the
    workbench number if that is the case"""
    return mdl.ClientInfo(
        status_code=status.HTTP_200_OK,
        detail=f"Requested ip address is known as workbench no. {WORKBENCH.number}",
        workbench_no=WORKBENCH.number,
    )


@api.post("/workbench/hid_event", response_model=mdl.GenericResponse, tags=["workbench"])
async def handle_hid_event(event: mdl.HidEvent) -> mdl.GenericResponse:
    """Parse the event dict JSON"""
    logger.debug(f"Received event dict:\n{event.json()}")
    # handle the event in accord with it's source
    sender: tp.Optional[str] = utils.identify_sender(event.name)

    try:
        if sender == "rfid_reader":
            logger.debug(f"Handling RFID event. String: {event.string}")

            if WORKBENCH.employee is not None:
                WORKBENCH.log_out()
            else:
                employee: Employee = await MongoDbWrapper().get_employee_by_card_id(event.string)
                WORKBENCH.log_in(employee)

        elif sender == "barcode_reader":
            logger.debug(f"Handling barcode event. String: {event.string}")

            if not utils.is_a_ean13_barcode(event.string):
                logger.warning(f"'{event.string}' is not a EAN13 barcode and cannot be an internal unit ID.")
            elif WORKBENCH.state is states.AUTHORIZED_IDLING_STATE:
                unit = await get_unit_by_internal_id(event.string)
                WORKBENCH.assign_unit(unit)
            elif WORKBENCH.state is states.UNIT_ASSIGNED_IDLING_STATE:
                WORKBENCH.remove_unit()
                unit = await get_unit_by_internal_id(event.string)
                WORKBENCH.assign_unit(unit)
            elif WORKBENCH.state is states.PRODUCTION_STAGE_ONGOING_STATE:
                await WORKBENCH.end_operation()
            else:
                logger.error(f"Received input {event.string}. Ignoring event since no one is authorized.")

        else:
            message: str = "Sender of the event dict is not mentioned in the config. Request ignored."
            return mdl.GenericResponse(status_code=status.HTTP_404_NOT_FOUND, detail=message)

        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Hid event has been handled as expected")

    except StateForbiddenError as e:
        return mdl.GenericResponse(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app:api", host=config.api_server.ip, port=config.api_server.port)
