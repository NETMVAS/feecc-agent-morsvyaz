import logging
import typing as tp
from dataclasses import dataclass
from datetime import datetime as dt
from uuid import uuid4

from . import _external_io_operations as external_io
from ._Employee import Employee
from ._Passport import Passport
from ._Types import Config


@dataclass
class ProductionStage:
    production_stage_name: str
    employee_name: str
    session_start_time: str
    session_end_time: str
    video_hashes: tp.Union[tp.List[str], None] = None
    additional_info: tp.Union[tp.Dict[str, tp.Any], None] = None


class Unit:
    """Unit class corresponds to one uniquely identifiable physical production unit"""

    def __init__(self, config: Config, uuid: str = "") -> None:
        self._config = config

        # product data
        self.uuid: str = uuid or self._generate_uuid()
        self.employee: tp.Optional[Employee] = None
        self.model: str = ""
        self.unit_biography: tp.List[ProductionStage] = []
        self._keyword = ""
        self._associated_passport = Passport(self)
        self._print_barcode()

    def _print_barcode(self) -> None:
        """print barcode with own int. id"""
        barcode = Barcode(self.internal_id)
        barcode.print_barcode(self._config)

    @property
    def internal_id(self) -> str:
        """get own internal id using own uuid"""
        return str(int(self.uuid, 16))[:13]

    @property
    def current_operation(self) -> tp.Optional[ProductionStage]:
        if self.unit_biography:
            return self.unit_biography[-1]
        else:
            return None

    @current_operation.setter
    def current_operation(self, current_operation: ProductionStage) -> None:
        self.unit_biography.append(current_operation)

    @staticmethod
    def _generate_uuid() -> str:
        return uuid4().hex

    @staticmethod
    def _current_timestamp() -> str:
        """generate formatted timestamp for the invocation moment"""

        timestamp: str = dt.now().strftime("%d-%m-%Y %H:%M:%S")
        return timestamp

    def start_session(
            self,
            production_stage_name: str,
            additional_info: tp.Union[tp.Dict[str, tp.Any], None] = None
    ) -> None:
        """begin the provided operation and save data about it"""

        logging.info(f"Starting production stage {production_stage_name} for unit with int. id {self.internal_id}")
        operation = ProductionStage(
            production_stage_name=production_stage_name,
            employee_name=self._associated_passport.encode_employee(),
            session_start_time=self._current_timestamp(),
            session_end_time=self._current_timestamp(),
            additional_info=additional_info
        )

        logging.debug(str(operation))
        self.current_operation = operation

    def end_session(
            self,
            video_hashes: tp.Union[tp.List[str], None] = None,
            additional_info: tp.Union[tp.Dict[str, tp.Any], None] = None
    ) -> None:
        """wrap up the session when video recording stops and save video data as well as session end timestamp"""

        self.current_operation.session_end_time = self._current_timestamp()

        if video_hashes:
            self.current_operation.video_hashes = video_hashes

        if additional_info:
            self.current_operation.additional_info = additional_info

        self._associated_passport.save()

    def upload(self) -> None:

        # upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics
        self._associated_passport.save()
        gateway = external_io.ExternalIoGateway(self._config)
        gateway.send(self._associated_passport.filename, self._keyword)
