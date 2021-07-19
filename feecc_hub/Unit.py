import logging
import typing as tp
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime as dt
from uuid import uuid4

from .Employee import Employee
from ._Barcode import Barcode
from ._Passport import Passport
from ._Types import Config
from ._external_io_operations import ExternalIoGateway
from .exceptions import OperationNotFoundError


@dataclass
class ProductionStage:
    name: str
    employee_name: str
    session_start_time: str
    session_end_time: tp.Optional[str] = None
    video_hashes: tp.Optional[tp.List[str]] = None
    additional_info: tp.Optional[tp.Dict[str, tp.Any]] = None
    id: str = uuid4().hex

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
                logging.error(
                    f"Cannot update attribute {key}, class {self.__class__.__name__} has no attribute {key}"
                )


class Unit:
    """Unit class corresponds to one uniquely identifiable physical production unit"""

    def __init__(self, config: Config, model: str, uuid: str = "") -> None:
        self._config: Config = config

        # product data
        self.uuid: str = uuid or self._generate_uuid()
        self.employee: tp.Optional[Employee] = None
        self.model: str = model
        self.unit_biography: tp.List[ProductionStage] = []
        self._associated_passport: Passport = Passport(self)

        if self._config["print_barcode"]["enable"]:
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

    @property
    def associated_barcode(self) -> Barcode:
        barcode = Barcode(str(int(self.uuid, 16))[:12])
        return barcode

    @property
    def internal_id(self) -> str:
        """get own internal id using own uuid"""
        return str(self.associated_barcode.barcode.get_fullcode())

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

    def start_session(
        self,
        production_stage_name: str,
        employee_code_name: str,
        additional_info: tp.Optional[tp.Dict[str, tp.Any]] = None,
    ) -> None:
        """begin the provided operation and save data about it"""
        logging.info(
            f"Starting production stage {production_stage_name} for unit with int. id "
            f"{self.internal_id}, additional info {additional_info}"
        )

        operation = ProductionStage(
            name=production_stage_name,
            employee_name=employee_code_name,
            session_start_time=ProductionStage.timestamp(),
            additional_info=additional_info,
        )

        logging.debug(str(operation))
        self.current_operation = operation

    def end_session(
        self,
        video_hashes: tp.Optional[tp.List[str]] = None,
        additional_info: tp.Optional[tp.Dict[str, tp.Any]] = None,
    ) -> None:
        """
        wrap up the session when video recording stops and save video data
        as well as session end timestamp
        """
        if self.current_operation is None:
            raise ValueError("No ongoing operations found")

        logging.info(f"Ending production stage {self.current_operation.name}")
        operation = deepcopy(self.current_operation)
        operation.session_end_time = ProductionStage.timestamp()

        if video_hashes:
            operation.video_hashes = video_hashes

        if additional_info:
            if operation.additional_info is not None:
                operation.additional_info = {
                    **operation.additional_info,
                    **additional_info,
                }
            else:
                operation.additional_info = additional_info

        self.unit_biography[-1] = operation
        logging.debug(f"Unit biography stage count is now {len(self.unit_biography)}")

        self._associated_passport.save()
        self.employee = None

    def upload(self) -> None:

        # upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics
        self._associated_passport.save()
        gateway = ExternalIoGateway(self._config)
        gateway.send(self._associated_passport.file)
