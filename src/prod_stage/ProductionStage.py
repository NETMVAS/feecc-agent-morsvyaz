import datetime as dt
from dataclasses import dataclass, field

from src.feecc_workbench.Types import AdditionalInfo


@dataclass
class ProductionStage:
    name: str
    parent_unit_uuid: str
    number: int
    employee_name: str | None = None
    session_start_time: str | None = None
    session_end_time: str | None = None
    ended_prematurely: bool = False
    stage_data: AdditionalInfo | None = None
    creation_time: dt.datetime = field(default_factory=lambda: dt.datetime.now())
    completed: bool = False
