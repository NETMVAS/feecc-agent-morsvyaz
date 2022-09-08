import datetime as dt
from dataclasses import dataclass, field
from uuid import uuid4

from .Types import AdditionalInfo


@dataclass
class ProductionStage:
    name: str
    parent_unit_uuid: str
    number: int
    schema_stage_id: str
    employee_name: str | None = None
    session_start_time: str | None = None
    session_end_time: str | None = None
    ended_prematurely: bool = False
    video_hashes: list[str] | None = None
    additional_info: AdditionalInfo | None = None
    id: str = field(default_factory=lambda: uuid4().hex)  # noqa: A003
    is_in_db: bool = False
    creation_time: dt.datetime = field(default_factory=lambda: dt.datetime.now())
    completed: bool = False
