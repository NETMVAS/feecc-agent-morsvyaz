from __future__ import annotations

import logging
import typing as tp

from . import _State as State
from .Employee import Employee
from .Types import AdditionalInfo, Config, ConfigSection
from .Unit import Unit
from ._Agent import Agent
from ._Camera import Camera
from .exceptions import AgentBusyError, EmployeeUnauthorizedError, UnitNotFoundError

if tp.TYPE_CHECKING:
    from .Hub import Hub
    from .database import DbWrapper


class WorkBench:
    """
    Work bench is a union of an Employee, working at it,
    Camera attached to it and associated Agent.
    It provides highly abstract interface for interaction with them
    """

    def __init__(self, associated_hub: Hub, workbench_config: tp.Dict[str, tp.Any]) -> None:
        self._workbench_config: tp.Dict[str, tp.Any] = workbench_config
        self.number: int = self._workbench_config["workbench number"]
        self._associated_hub: Hub = associated_hub
        self._associated_camera: tp.Optional[Camera] = self._get_camera()
        self.employee: tp.Optional[Employee] = None
        self.agent: Agent = self._get_agent()
        logging.info(f"Workbench no. {self.number} initialized")
        logging.debug(f"Raw workbench configuration:\n{self._workbench_config}")

    @property
    def config(self) -> Config:
        return self._associated_hub.config

    @property
    def camera(self) -> tp.Optional[Camera]:
        return self._associated_camera

    @property
    def unit_in_operation(self) -> str:
        if self.agent.associated_unit is None:
            return ""
        else:
            return str(self.agent.associated_unit.internal_id)

    @property
    def is_operation_ongoing(self) -> bool:
        return bool(self.unit_in_operation)

    @property
    def state_name(self) -> str:
        return self.agent.state_name

    @property
    def state_description(self) -> str:
        return self.agent.state_description

    def _get_camera(self) -> tp.Optional[Camera]:
        camera_config: tp.Optional[ConfigSection] = self._workbench_config["hardware"]["camera"]
        return Camera(camera_config) if camera_config else None

    def _get_agent(self) -> Agent:
        agent = Agent(self)
        agent.execute_state(State.AwaitLogin)
        return agent

    def start_shift(self, employee: Employee) -> None:
        """authorize employee"""
        if self.employee is not None:
            message = f"Employee {employee.rfid_card_id} is already logged in at the workbench no. {self.number}"
            raise AgentBusyError(message)

        self.employee = employee
        logging.info(
            f"Employee {employee.rfid_card_id} is logged in at the workbench no. {self.number}"
        )
        self.agent.execute_state(State.AuthorizedIdling)

    def end_shift(self) -> None:
        """log out employee, finish ongoing operations if any"""
        if self.agent.state_name == "ProductionStageOngoing":
            self.end_operation(self.unit_in_operation)

        if self.employee is None:
            error_message = (
                f"Cannot log out employee at the workbench no. {self.number}. No one logged in"
            )
            raise EmployeeUnauthorizedError(error_message)
        else:
            self.employee = None

        self.agent.execute_state(State.AwaitLogin)

    def start_operation(
        self, unit: Unit, production_stage_name: str, additional_info: AdditionalInfo
    ) -> None:
        """begin work on the provided unit"""
        logging.info(
            f"Starting operation {production_stage_name} on the unit {unit.internal_id} at the workbench no. {self.number}"
        )

        # check if employee is logged in
        if self.employee is None:
            message = f"Cannot start an operation: No employee is logged in at the Workbench {self.number}"
            raise EmployeeUnauthorizedError(message)

        # check if there are no ongoing operations
        if self.is_operation_ongoing:
            message = f"Cannot start an operation: An operation is already ongoing at the Workbench {self.number}"
            raise AgentBusyError(message)

        # start operation
        self.agent.execute_state(
            State.ProductionStageStarting,
            True,
            unit,
            self.employee,
            production_stage_name,
            additional_info,
        )

        logging.info(
            f"Started operation {production_stage_name} on the unit {unit.internal_id} at the workbench no. {self.number}"
        )

    def end_operation(
        self, unit_internal_id: str, additional_info: tp.Optional[AdditionalInfo] = None
    ) -> None:
        """end work on the provided unit"""
        # make sure requested unit is associated with this workbench
        if unit_internal_id == self.unit_in_operation:
            database: DbWrapper = self._associated_hub.database

            self.agent.execute_state(State.ProductionStageEnding, True, database, additional_info)

        else:
            message = f"Unit with int. id {unit_internal_id} isn't associated with the Workbench {self.number}"
            logging.error(message)
            logging.debug(f"Unit in operation on workbench {self.number}: {self.unit_in_operation}")
            raise UnitNotFoundError(message)
