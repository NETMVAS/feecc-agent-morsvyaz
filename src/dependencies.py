from dataclasses import asdict

from fastapi import HTTPException, status
from loguru import logger

from feecc_workbench import models
from feecc_workbench.config import CONFIG
from feecc_workbench.database import MongoDbWrapper
from feecc_workbench.Employee import Employee
from feecc_workbench.exceptions import EmployeeNotFoundError, UnitNotFoundError
from feecc_workbench.Messenger import messenger
from feecc_workbench.Unit import Unit
from feecc_workbench.unit_utils import UnitStatus
from feecc_workbench.utils import is_a_ean13_barcode


async def get_unit_by_internal_id(unit_internal_id: str) -> Unit:
    try:
        return await MongoDbWrapper().get_unit_by_internal_id(unit_internal_id)

    except UnitNotFoundError as e:
        messenger.warning("Изделие не найдено")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


async def get_employee_by_card_id(employee_data: models.EmployeeID) -> models.EmployeeWCardModel:
    try:
        employee: Employee = await MongoDbWrapper().get_employee_by_card_id(employee_data.employee_rfid_card_no)
        return models.EmployeeWCardModel(**asdict(employee))

    except EmployeeNotFoundError as e:
        messenger.warning("Сотрудник не найден")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


async def get_schema_by_id(schema_id: str) -> models.ProductionSchema:
    """get the specified production schema"""
    try:
        return await MongoDbWrapper().get_schema_by_id(schema_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


async def get_revision_pending_units() -> list[dict[str, str]]:
    """get all the units headed for revision"""
    return await MongoDbWrapper().get_unit_ids_and_names_by_status(UnitStatus.revision)  # type: ignore


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
                messenger.default("Не является штрих-кодом")
                logger.warning(message)
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

            event.name = sender_name
            return event

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sender device {event.name} is unknown")
