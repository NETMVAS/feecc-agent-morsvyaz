import typing as tp
from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    """State description container"""

    name: str
    description: str


AWAIT_LOGIN_STATE = State(
    name="AwaitLogin",
    description="State when the workbench is empty and waiting for an employee authorization",
)

AUTHORIZED_IDLING_STATE = State(
    name="AuthorizedIdling",
    description="State when an employee was authorized at the workbench but doing nothing",
)

UNIT_ASSIGNED_IDLING_STATE = State(
    name="UnitAssignedIdling",
    description="State when a unit is already assigned to the workbench but there is no ongoing operation",
)

PRODUCTION_STAGE_ONGOING_STATE = State(
    name="ProductionStageOngoing",
    description="State when there is an active job ongoing",
)

STATE_TRANSITION_MAP: tp.Dict[State, tp.List[State]] = {
    AWAIT_LOGIN_STATE: [AUTHORIZED_IDLING_STATE],
    AUTHORIZED_IDLING_STATE: [UNIT_ASSIGNED_IDLING_STATE, AWAIT_LOGIN_STATE],
    UNIT_ASSIGNED_IDLING_STATE: [AUTHORIZED_IDLING_STATE, AWAIT_LOGIN_STATE, PRODUCTION_STAGE_ONGOING_STATE],
    PRODUCTION_STAGE_ONGOING_STATE: [UNIT_ASSIGNED_IDLING_STATE],
}
