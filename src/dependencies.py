from dataclasses import asdict

from fastapi import HTTPException, status
from loguru import logger

from src.database import models
from feecc_workbench.config import CONFIG
from .unit.unit_wrapper import unit_wrapper
from .employee.employee_wrapper import employee_wrapper
from .prod_schema.prod_schema_wrapper import prod_schema_wrapper
from src.employee.Employee import Employee
from feecc_workbench.exceptions import EmployeeNotFoundError, UnitNotFoundError
from feecc_workbench.Messenger import messenger
from feecc_workbench.translation import translation
from src.unit.Unit import Unit
from src.unit.unit_utils import UnitStatus
from feecc_workbench.utils import is_a_ean13_barcode


def get_unit_by_internal_id(unit_internal_id: str) -> Unit:
    try:
        return unit_wrapper.get_unit_by_internal_id(unit_internal_id)

    except UnitNotFoundError as e:
        messenger.warning(translation("NoUnit"))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


def get_employee_by_card_id(employee_data: models.EmployeeID) -> models.EmployeeWCardModel:
    try:
        employee: Employee = employee_wrapper.get_employee_by_card_id(employee_data.employee_rfid_card_no)
        return models.EmployeeWCardModel(**asdict(employee))

    except EmployeeNotFoundError as e:
        messenger.warning(translation("NoEmployee"))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


def get_schema_by_id(schema_id: str) -> models.ProductionSchema:
    """get the specified production schema"""
    try:
        return prod_schema_wrapper.get_schema_by_id(schema_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


def get_revision_pending_units() -> list[dict[str, str]]:
    """get all the units headed for revision"""
    return unit_wrapper.get_unit_ids_and_names_by_status(UnitStatus.revision)  # type: ignore


def identify_sender(event: models.HidEvent) -> models.HidEvent:
    """identify, which device the input is coming from and if it is known return its role"""
    logger.debug(f"Received event dict: {event.dict(include={'string', 'name'})}")

    known_hid_devices: dict[str, str] = {
        "rfid_reader": CONFIG.hid_devices.rfid_reader,
        "barcode_reader": CONFIG.hid_devices.barcode_reader,
    }

    for sender_name, device_name in known_hid_devices.items():
        if device_name == event.name:
            if sender_name == "barcode_reader" and not is_a_ean13_barcode(event.string):
                message = f"'{event.string}' is not a EAN13 barcode and cannot be an internal unit ID."
                messenger.default(translation("NotBarcode"))
                logger.warning(message)
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

            event.name = sender_name
            return event

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sender device {event.name} is unknown")
