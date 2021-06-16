import logging
import typing as tp

import State
from Agent import Agent
from Employee import Employee
from Hub import Hub
from Types import Config
from Unit import Unit
from modules.Camera import Camera


class WorkBench:
    """
    Work bench is a union of an Employee, working at it,
    Camera attached to it and associated Agent.
    It provides highly abstract interface for interaction with them
    """

    def __init__(self, associated_hub: Hub, workbench_config: tp.Dict[str, tp.Any]) -> None:
        self._workbench_config: tp.Dict[str, tp.Any] = workbench_config
        self.number: int = self._workbench_config["workbench number"]
        self._associated_agent: Agent = self._get_agent()
        self._associated_employee: tp.Union[Employee, None] = None
        self._associated_hub: Hub = associated_hub
        self._associated_camera: tp.Union[Camera, None] = self._get_camera()
        logging.info(f"Workbench no. {self.number} initialized")
        logging.debug(f"Raw workbench configuration:\n{self._workbench_config}")

    @property
    def hub_config(self) -> Config:
        return self._associated_hub.config

    @property
    def employee(self) -> Employee:
        return self._associated_employee

    @property
    def camera(self) -> Camera:
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
        return self._associated_agent.state

    @property
    def state_description(self) -> str:
        return self._associated_agent.state_description

    def _get_camera(self) -> tp.Union[Camera, None]:
        camera_config: tp.Union[tp.Dict[str, tp.Any], None] = self._workbench_config["hardware"]["camera"]

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

        if self._associated_agent.state == 2:
            self.end_operation(self.unit_in_operation)

        self._associated_employee = None
        self._associated_agent.execute_state(State.State0)

    # todo
    def start_operation(self, unit: Unit, production_stage_name: str, additional_info: tp.Dict[str, tp.Any]) -> None:
        """begin work on the provided unit"""

        pass

    # todo
    def end_operation(self, unit_internal_id: str) -> None:
        """end work on the provided unit"""

        pass
