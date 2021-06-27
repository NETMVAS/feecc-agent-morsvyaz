from __future__ import annotations

import logging
import typing as tp

from . import _State as State
from .Unit import Unit
from ._Agent import Agent
from ._Camera import Camera
from ._Employee import Employee
from ._Types import Config
from .exceptions import EmployeeUnauthorizedError, AgentBusyError

if tp.TYPE_CHECKING:
    from .Hub import Hub


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
        self._associated_employee: tp.Optional[Employee] = None
        self._associated_agent: Agent = self._get_agent()
        logging.info(f"Workbench no. {self.number} initialized")
        logging.debug(f"Raw workbench configuration:\n{self._workbench_config}")

    @property
    def config(self) -> Config:
        return self._associated_hub.config

    @property
    def employee(self) -> tp.Optional[Employee]:
        return self._associated_employee

    @property
    def camera(self) -> tp.Optional[Camera]:
        return self._associated_camera

    @property
    def unit_in_operation(self) -> str:
        if self._associated_agent.associated_unit is None:
            return ""
        else:
            return self._associated_agent.associated_unit.internal_id

    @property
    def is_operation_ongoing(self) -> bool:
        return bool(self.unit_in_operation)

    @property
    def state_number(self) -> int:
        return self._associated_agent.state_no

    @property
    def state_description(self) -> str:
        return self._associated_agent.state_description

    def _get_camera(self) -> tp.Optional[Camera]:
        camera_config: tp.Optional[tp.Dict[str, tp.Any]] = self._workbench_config["hardware"][
            "camera"
        ]

        if camera_config is None:
            return None
        else:
            camera = Camera(camera_config)
            return camera

    def _get_agent(self) -> Agent:
        agent = Agent(self)
        agent.execute_state(State.State0)
        return agent

    def start_shift(self, employee_rfid_card_id: str) -> None:
        """authorize employee"""
        self._associated_employee = Employee(employee_rfid_card_id)
        self._associated_agent.execute_state(State.State1)

    def end_shift(self) -> None:
        """log out employee, finish ongoing operations if any"""
        if self._associated_agent.state_no == 2:
            self.end_operation(self.unit_in_operation)

        self._associated_employee = None
        self._associated_agent.execute_state(State.State0)

    def start_operation(
        self, unit: Unit, production_stage_name: str, additional_info: tp.Dict[str, tp.Any]
    ) -> None:
        """begin work on the provided unit"""
        logging.info(
            f"Starting operation {production_stage_name} on the unit {unit.internal_id} at the workbench no. {self.number}"
        )

        # check if employee is logged in
        if not (self.employee and self.employee.is_logged_in):
            message = f"Cannot start an operation: No employee is logged in at the Workbench {self.number}"
            raise EmployeeUnauthorizedError(message)

        # check if there are no ongoing operations
        if self.is_operation_ongoing:
            message = f"Cannot start an operation: An operation is already ongoing at the Workbench {self.number}"
            logging.error(message)
            raise AgentBusyError(message)

        # assign unit
        self._associated_agent.associated_unit = unit

        # start operation at the unit
        self._associated_agent.associated_unit.start_session(production_stage_name, additional_info)

        # start recording video
        self._associated_agent.execute_state(State.State2)

        logging.info(
            f"Started operation {production_stage_name} on the unit {unit.internal_id} at the workbench no. {self.number}"
        )

    def end_operation(self, unit_internal_id: str) -> None:
        """end work on the provided unit"""
        # make sure requested unit is associated with this workbench
        if unit_internal_id == self.unit_in_operation:
            self._associated_agent.execute_state(State.State3)

        else:
            message = f"Unit with int. id {unit_internal_id} is not associated with the Workbench no.{self.number}"
            logging.error(message)
            raise ValueError(message)
