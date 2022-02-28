import datetime as dt
import typing as tp
from dataclasses import dataclass, field
from uuid import uuid4

from .Types import AdditionalInfo


@dataclass
class ProductionStage:
    name: str
    parent_unit_uuid: str
    number: int
    schema_stage_id: str
    employee_name: tp.Optional[str] = None
    session_start_time: tp.Optional[str] = None
    session_end_time: tp.Optional[str] = None
    ended_prematurely: bool = False
    video_hashes: tp.Optional[tp.List[str]] = None
    additional_info: tp.Optional[AdditionalInfo] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    is_in_db: bool = False
    creation_time: dt.datetime = field(default_factory=lambda: dt.datetime.now())
    completed: bool = False
