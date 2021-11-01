import typing as tp

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from _logging import CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG
from dependencies import get_employee_by_card_id, get_schema_by_id, get_unit_by_internal_id, identify_sender
from feecc_workbench import models as mdl, states
from feecc_workbench.Employee import Employee
from feecc_workbench.Unit import Unit
from feecc_workbench.WorkBench import WorkBench
from feecc_workbench.database import MongoDbWrapper
from feecc_workbench.exceptions import EmployeeNotFoundError, StateForbiddenError, UnitNotFoundError

# apply logging configuration
logger.configure(handlers=[CONSOLE_LOGGING_CONFIG, FILE_LOGGING_CONFIG])

# global variables
app = FastAPI(title="Feecc Workbench daemon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKBENCH = WorkBench()


@app.on_event("startup")
def startup_event() -> None:
    MongoDbWrapper()


@app.post("/unit/new/{schema_id}", response_model=tp.Union[mdl.UnitOut, mdl.GenericResponse], tags=["unit"])  # type: ignore
async def create_unit(
    schema: mdl.ProductionSchema = Depends(get_schema_by_id),
) -> tp.Union[mdl.UnitOut, mdl.GenericResponse]:
    """handle new Unit creation"""
    try:
        unit: Unit = await WORKBENCH.create_new_unit(schema)
        logger.info(f"Initialized new unit with internal ID {unit.internal_id}")
        return mdl.UnitOut(
            status_code=status.HTTP_200_OK,
            detail="New unit created successfully",
            unit_internal_id=unit.internal_id,
        )

    except Exception as e:
        logger.error(f"Exception occurred while creating new Unit: {e}")
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/unit/{unit_internal_id}/info", response_model=mdl.UnitInfo, tags=["unit"])
def get_unit_data(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.UnitInfo:
    """return data for a Unit with matching ID"""
    return mdl.UnitInfo(
        status_code=status.HTTP_200_OK,
        detail="Unit data retrieved successfully",
        unit_internal_id=unit.internal_id,
        unit_biography=[stage.name for stage in unit.biography],
        unit_components=unit.components_schema_ids or None,
        schema_id=unit.schema.schema_id,
    )


@app.post("/unit/upload", response_model=mdl.GenericResponse, tags=["unit"])
async def unit_upload_record() -> mdl.GenericResponse:
    """handle Unit lifecycle end"""
    try:
        if WORKBENCH.employee is None:
            raise StateForbiddenError("Employee is not authorized on the workbench")

        await WORKBENCH.upload_unit_passport()
        return mdl.GenericResponse(
            status_code=status.HTTP_200_OK, detail=f"Uploaded data for unit {WORKBENCH.unit.internal_id}"
        )

    except Exception as e:
        message: str = f"Can't handle unit upload. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@app.post("/unit/assign-component/{unit_internal_id}", response_model=mdl.GenericResponse, tags=["unit"])
async def assign_component(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.GenericResponse:
    """assign a unit as a component to the composite unit"""
    if WORKBENCH.state is not states.GATHER_COMPONENTS_STATE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Component assignment can only be done while the workbench is in state 'GatherComponents'",
        )

    try:
        await WORKBENCH.assign_component_to_unit(unit)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Component has been assigned")

    except Exception as e:
        message: str = f"An error occurred during component assignment: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@app.post("/employee/info", response_model=mdl.EmployeeOut, tags=["employee"])
def get_employee_data(employee: mdl.EmployeeWCardModel = Depends(get_employee_by_card_id)) -> mdl.EmployeeOut:
    """return data for an Employee with matching ID card"""
    return mdl.EmployeeOut(
        status_code=status.HTTP_200_OK, detail="Employee retrieved successfully", employee_data=employee
    )


@app.post("/employee/log-in", response_model=tp.Union[mdl.EmployeeOut, mdl.GenericResponse], tags=["employee"])  # type: ignore
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


@app.post("/employee/log-out", response_model=mdl.GenericResponse, tags=["employee"])
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


@app.get("/workbench/status", response_model=mdl.WorkbenchOut, tags=["workbench"])
def get_workbench_status() -> mdl.WorkbenchOut:
    """handle providing status of the given Workbench"""
    unit = WORKBENCH.unit
    return mdl.WorkbenchOut(
        state=WORKBENCH.state.name,
        state_description=WORKBENCH.state.description,
        employee_logged_in=bool(WORKBENCH.employee),
        employee=WORKBENCH.employee.data if WORKBENCH.employee else None,
        operation_ongoing=WORKBENCH.state is states.PRODUCTION_STAGE_ONGOING_STATE,
        unit_internal_id=unit.internal_id if unit else None,
        unit_biography=[stage.name for stage in unit.biography] if unit else None,
        unit_components=unit.assigned_components() if unit else None,
    )


@app.post("/workbench/assign-unit/{unit_internal_id}", response_model=mdl.GenericResponse, tags=["workbench"])
def assign_unit(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.GenericResponse:
    """assign the provided unit to the workbench"""
    try:
        WORKBENCH.assign_unit(unit)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=f"Unit {unit.internal_id} has been assigned")

    except Exception as e:
        message: str = f"An error occurred during unit assignment: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@app.post("/workbench/remove-unit", response_model=mdl.GenericResponse, tags=["workbench"])
def remove_unit() -> mdl.GenericResponse:
    """remove the unit from the workbench"""
    try:
        WORKBENCH.remove_unit()
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Unit has been removed")

    except Exception as e:
        message: str = f"An error occurred during unit removal: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@app.post("/workbench/start-operation", response_model=mdl.GenericResponse, tags=["workbench"])
async def start_operation(workbench_details: mdl.WorkbenchExtraDetails) -> mdl.GenericResponse:
    """handle start recording operation on a Unit"""
    try:
        await WORKBENCH.start_operation(workbench_details.production_stage_name, workbench_details.additional_info)
        unit = WORKBENCH.unit
        message: str = f"Started operation '{workbench_details.production_stage_name}' on Unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@app.post("/workbench/end-operation", response_model=mdl.GenericResponse, tags=["workbench"])
async def end_operation(workbench_data: mdl.WorkbenchExtraDetailsWithoutStage) -> mdl.GenericResponse:
    """handle end recording operation on a Unit"""
    try:
        await WORKBENCH.end_operation(workbench_data.additional_info)
        unit = WORKBENCH.unit
        message: str = f"Ended current operation on unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle end record request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@app.get("/workbench/production-schemas/names", response_model=mdl.SchemasList, tags=["workbench"])
async def get_schemas() -> mdl.SchemasList:
    """get all available schemas"""
    all_schemas = {schema.schema_id: schema for schema in await MongoDbWrapper().get_all_schemas()}
    handled_schemas = set()

    def get_schema_list_entry(schema: mdl.ProductionSchema) -> mdl.SchemaListEntry:
        nonlocal all_schemas, handled_schemas
        included_schemas: tp.Optional[tp.List[mdl.SchemaListEntry]] = (
            [get_schema_list_entry(all_schemas[s_id]) for s_id in schema.required_components_schema_ids]
            if schema.is_composite
            else None
        )
        handled_schemas.add(schema.schema_id)
        return mdl.SchemaListEntry(
            schema_id=schema.schema_id,
            schema_name=schema.unit_name,
            included_schemas=included_schemas,
        )

    available_schemas = [
        get_schema_list_entry(schema)
        for schema in sorted(all_schemas.values(), key=lambda s: bool(s.is_composite), reverse=True)
        if schema.schema_id not in handled_schemas
    ]

    return mdl.SchemasList(
        status_code=status.HTTP_200_OK,
        detail=f"Gathered {len(all_schemas)} schemas",
        available_schemas=available_schemas,
    )


@app.get(
    "/workbench/production-schemas/{schema_id}",
    response_model=tp.Union[mdl.ProductionSchemaResponse, mdl.GenericResponse],  # type: ignore
    tags=["workbench"],
)
async def get_schema(
    schema: mdl.ProductionSchema = Depends(get_schema_by_id),
) -> tp.Union[mdl.ProductionSchemaResponse, mdl.GenericResponse]:
    """get schema by it's ID"""
    return mdl.ProductionSchemaResponse(
        status_code=status.HTTP_200_OK,
        detail=f"Found schema {schema.schema_id}",
        production_schema=schema,
    )


@app.post("/workbench/hid-event", response_model=mdl.GenericResponse, tags=["workbench"])
async def handle_hid_event(event: mdl.HidEvent = Depends(identify_sender)) -> mdl.GenericResponse:
    """Parse the event dict JSON"""
    logger.debug(f"Received event dict:\n{event.json()}")

    try:
        if event.name == "rfid_reader":
            logger.debug(f"Handling RFID event. String: {event.string}")

            if WORKBENCH.employee is not None:
                WORKBENCH.log_out()
            else:
                try:
                    employee: Employee = await MongoDbWrapper().get_employee_by_card_id(event.string)
                except EmployeeNotFoundError as e:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

                WORKBENCH.log_in(employee)

        elif event.name == "barcode_reader":
            logger.debug(f"Handling barcode event. String: {event.string}")

            if WORKBENCH.state is states.PRODUCTION_STAGE_ONGOING_STATE:
                await WORKBENCH.end_operation()
            else:
                try:
                    unit = await get_unit_by_internal_id(event.string)
                except UnitNotFoundError as e:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

                if WORKBENCH.state is states.AUTHORIZED_IDLING_STATE:
                    WORKBENCH.assign_unit(unit)
                elif WORKBENCH.state is states.UNIT_ASSIGNED_IDLING_STATE:
                    WORKBENCH.remove_unit()
                    WORKBENCH.assign_unit(unit)
                elif WORKBENCH.state is states.GATHER_COMPONENTS_STATE:
                    await WORKBENCH.assign_component_to_unit(unit)
                else:
                    logger.error(f"Received input {event.string}. Ignoring event since no one is authorized.")

        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Hid event has been handled as expected")

    except StateForbiddenError as e:
        return mdl.GenericResponse(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    except Exception as e:
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app:app", port=5000)
