import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from dependencies import get_schema_by_id, get_unit_by_internal_id, identify_sender
from feecc_workbench import models as mdl
from feecc_workbench.Employee import Employee
from feecc_workbench.Unit import Unit
from feecc_workbench.WorkBench import STATE_SWITCH_EVENT, WorkBench
from feecc_workbench.database import MongoDbWrapper
from feecc_workbench.exceptions import EmployeeNotFoundError, UnitNotFoundError
from feecc_workbench.states import State

WORKBENCH = WorkBench()

router = APIRouter(
    prefix="/workbench",
    tags=["workbench"],
)


def get_workbench_status_data() -> mdl.WorkbenchOut:
    unit = WORKBENCH.unit
    return mdl.WorkbenchOut(
        state=WORKBENCH.state.value,
        employee_logged_in=bool(WORKBENCH.employee),
        employee=WORKBENCH.employee.data if WORKBENCH.employee else None,
        operation_ongoing=WORKBENCH.state.value == State.PRODUCTION_STAGE_ONGOING_STATE.value,
        unit_internal_id=unit.internal_id if unit else None,
        unit_status=unit.status.value if unit else None,
        unit_biography=[stage.name for stage in unit.biography] if unit else None,
        unit_components=unit.assigned_components() if unit else None,
    )


@router.get("/status", response_model=mdl.WorkbenchOut, deprecated=True)
def get_workbench_status() -> mdl.WorkbenchOut:
    """
    handle providing status of the given Workbench

    DEPRECATED: Use SSE instead
    """
    return get_workbench_status_data()


async def state_update_generator(event: asyncio.Event) -> AsyncGenerator[str, None]:
    """State update event generator for SSE streaming"""
    logger.info("SSE connection to state streaming endpoint established.")

    try:
        while True:
            yield get_workbench_status_data().json()
            logger.debug("State notification sent to the SSE client")
            event.clear()
            await event.wait()

    except asyncio.CancelledError as e:
        logger.info(f"SSE connection to state streaming endpoint closed. {e}")


@router.get("/status/stream")
async def stream_workbench_status() -> EventSourceResponse:
    """Send updates on the workbench state into a SSE stream"""
    status_stream = state_update_generator(STATE_SWITCH_EVENT)
    return EventSourceResponse(status_stream)


@router.post("/assign-unit/{unit_internal_id}", response_model=mdl.GenericResponse)
def assign_unit(unit: Unit = Depends(get_unit_by_internal_id)) -> mdl.GenericResponse:
    """assign the provided unit to the workbench"""
    try:
        WORKBENCH.assign_unit(unit)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=f"Unit {unit.internal_id} has been assigned")

    except Exception as e:
        message: str = f"An error occurred during unit assignment: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@router.post("/remove-unit", response_model=mdl.GenericResponse)
def remove_unit() -> mdl.GenericResponse:
    """remove the unit from the workbench"""
    try:
        WORKBENCH.remove_unit()
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Unit has been removed")

    except Exception as e:
        message: str = f"An error occurred during unit removal: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@router.post("/start-operation", response_model=mdl.GenericResponse)
async def start_operation(workbench_details: mdl.WorkbenchExtraDetails) -> mdl.GenericResponse:
    """handle start recording operation on a Unit"""
    try:
        await WORKBENCH.start_operation(workbench_details.additional_info)
        unit = WORKBENCH.unit
        message: str = f"Started operation '{unit.next_pending_operation.name}' on Unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@router.post("/end-operation", response_model=mdl.GenericResponse)
async def end_operation(workbench_data: mdl.WorkbenchExtraDetailsWithoutStage) -> mdl.GenericResponse:
    """handle end recording operation on a Unit"""
    try:
        await WORKBENCH.end_operation(workbench_data.additional_info, workbench_data.premature_ending)
        unit = WORKBENCH.unit
        message: str = f"Ended current operation on unit {unit.internal_id}"
        logger.info(message)
        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail=message)

    except Exception as e:
        message = f"Couldn't handle end record request. An error occurred: {e}"
        logger.error(message)
        return mdl.GenericResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)


@router.get("/production-schemas/names", response_model=mdl.SchemasList)
async def get_schemas() -> mdl.SchemasList:
    """get all available schemas"""
    all_schemas = {schema.schema_id: schema for schema in await MongoDbWrapper().get_all_schemas()}
    handled_schemas = set()

    def get_schema_list_entry(schema: mdl.ProductionSchema) -> mdl.SchemaListEntry:
        nonlocal all_schemas, handled_schemas
        included_schemas: list[mdl.SchemaListEntry] | None = (
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


@router.get("/production-schemas/{schema_id}", response_model=mdl.ProductionSchemaResponse)
async def get_schema(schema: mdl.ProductionSchema = Depends(get_schema_by_id)) -> mdl.ProductionSchemaResponse:
    """get schema by its ID"""
    return mdl.ProductionSchemaResponse(
        status_code=status.HTTP_200_OK,
        detail=f"Found schema {schema.schema_id}",
        production_schema=schema,
    )


@router.post("/hid-event", response_model=mdl.GenericResponse)
async def handle_hid_event(event: mdl.HidEvent = Depends(identify_sender)) -> mdl.GenericResponse:
    """Parse the event dict JSON"""
    try:
        if event.name == "rfid_reader":
            logger.debug(f"Handling RFID event. String: {event.string}")

            if WORKBENCH.employee is not None:
                WORKBENCH.log_out()
            else:
                try:
                    employee: Employee = await MongoDbWrapper().get_employee_by_card_id(event.string)
                except EmployeeNotFoundError as e:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

                WORKBENCH.log_in(employee)

        elif event.name == "barcode_reader":
            logger.debug(f"Handling barcode event. String: {event.string}")

            if WORKBENCH.state == State.PRODUCTION_STAGE_ONGOING_STATE:
                await WORKBENCH.end_operation()
            else:
                try:
                    unit = await get_unit_by_internal_id(event.string)
                except UnitNotFoundError as e:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

                if WORKBENCH.state == State.AUTHORIZED_IDLING_STATE:
                    WORKBENCH.assign_unit(unit)
                elif WORKBENCH.state == State.UNIT_ASSIGNED_IDLING_STATE:
                    WORKBENCH.remove_unit()
                    WORKBENCH.assign_unit(unit)
                elif WORKBENCH.state == State.GATHER_COMPONENTS_STATE:
                    await WORKBENCH.assign_component_to_unit(unit)
                else:
                    logger.error(f"Received input {event.string}. Ignoring event since no one is authorized.")

        return mdl.GenericResponse(status_code=status.HTTP_200_OK, detail="Hid event has been handled as expected")

    except Exception as e:
        logger.error(e)
        return mdl.GenericResponse(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
