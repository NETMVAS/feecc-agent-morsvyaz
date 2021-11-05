import typing as tp
from dataclasses import asdict

from fastapi import HTTPException, status
from loguru import logger

from feecc_workbench import models
from feecc_workbench.Employee import Employee
from feecc_workbench.Unit import Unit
from feecc_workbench.config import config
from feecc_workbench.database import MongoDbWrapper
from feecc_workbench.exceptions import EmployeeNotFoundError, UnitNotFoundError
from feecc_workbench.utils import is_a_ean13_barcode


async def get_unit_by_internal_id(unit_internal_id: str) -> Unit:
    try:
        return await MongoDbWrapper().get_unit_by_internal_id(unit_internal_id)

    except UnitNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


async def get_employee_by_card_id(employee_data: models.EmployeeID) -> models.EmployeeWCardModel:
    try:
        employee: Employee = await MongoDbWrapper().get_employee_by_card_id(employee_data.employee_rfid_card_no)
        return models.EmployeeWCardModel(**asdict(employee))

    except EmployeeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


async def get_schema_by_id(schema_id: str) -> models.ProductionSchema:
    """get the specified production schema"""
    try:
        return await MongoDbWrapper().get_schema_by_id(schema_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


def identify_sender(event: models.HidEvent) -> models.HidEvent:
    """identify, which device the input is coming from and if it is known return it's role"""
    known_hid_devices: tp.Dict[str, str] = config.hid_devices_names.dict()

    for sender_name, device_name in known_hid_devices.items():
        if device_name == event.name:
            if sender_name == "barcode_reader" and not is_a_ean13_barcode(event.string):
                message = f"'{event.string}' is not a EAN13 barcode and cannot be an internal unit ID."
                logger.warning(message)
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)

            event.name = sender_name
            return event

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sender device {event.name} is unknown")
