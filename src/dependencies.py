from dataclasses import asdict

from fastapi import HTTPException, Request, status

from feecc_workbench import models
from feecc_workbench.Employee import Employee
from feecc_workbench.Unit import Unit
from feecc_workbench.WorkBench import WorkBench
from feecc_workbench.database import MongoDbWrapper
from feecc_workbench.exceptions import EmployeeNotFoundError, UnitNotFoundError


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


def validate_sender(request: Request) -> None:
    if request.client.host != WorkBench().ip:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="All orders shall come from the localhost")
