from __future__ import annotations

import typing as tp
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime as dt
from uuid import uuid4

from loguru import logger

from ._Barcode import Barcode
from ._external_io_operations import ExternalIoGateway
from ._Passport import Passport
from .Employee import Employee
from .exceptions import OperationNotFoundError
from .Types import AdditionalInfo, Config

if tp.TYPE_CHECKING:
    from .database import DbWrapper


@dataclass
class ProductionStage:
    name: str
    employee_name: str
    parent_unit_uuid: str
    session_start_time: str
    session_end_time: tp.Optional[str] = None
    video_hashes: tp.Optional[tp.List[str]] = None
    additional_info: tp.Optional[AdditionalInfo] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    is_in_db: bool = False

    @staticmethod
    def timestamp() -> str:
        """generate formatted timestamp for the invocation moment"""
        timestamp: str = dt.now().strftime("%d-%m-%Y %H:%M:%S")
        return timestamp

    def update_attributes(self, new_values: tp.Dict[str, tp.Any]) -> None:
        for key, value in new_values.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.error(
                    f"Cannot update attribute {key}, class {self.__class__.__name__} has no attribute {key}"
                )


@dataclass
class Unit:
    """Unit class corresponds to one uniquely identifiable physical production unit"""

    _config: Config
    model: str
    uuid: str = field(default_factory=lambda: uuid4().hex)
    internal_id: tp.Optional[str] = None
    employee: tp.Optional[Employee] = None
    unit_biography: tp.List[ProductionStage] = field(default_factory=list)
    _associated_passport: tp.Optional[Passport] = None
    is_in_db: bool = False

    def __post_init__(self) -> None:
        self._associated_passport = Passport(self)

        if self.internal_id is None:
            self.internal_id = self.get_internal_id()

        if self._config["print_barcode"]["enable"] and not self.is_in_db:
            self._print_barcode()

    def production_stage(self, id_: str) -> ProductionStage:
        """find production stage with provided ID"""
        for stage in self.unit_biography:
            if stage.id == id_:
                return stage

        raise OperationNotFoundError

    def _print_barcode(self) -> None:
        """print barcode with own int. id"""
        self.associated_barcode.print_barcode(self._config)

    def get_internal_id(self) -> str:
        """get own internal id using own uuid"""
        return str(self.associated_barcode.barcode.get_fullcode())

    @property
    def associated_barcode(self) -> Barcode:
        barcode = Barcode(str(int(self.uuid, 16))[:12])
        return barcode

    @property
    def current_operation(self) -> tp.Optional[ProductionStage]:
        if self.unit_biography:
            return self.unit_biography[-1]
        else:
            return None

    @current_operation.setter
    def current_operation(self, current_operation: ProductionStage) -> None:
        self.unit_biography.append(current_operation)

    def upload(self) -> None:
        """upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics"""
        if self._associated_passport is not None:
            self._associated_passport.save()
            gateway = ExternalIoGateway(self._config)
            gateway.send(self._associated_passport.file)
