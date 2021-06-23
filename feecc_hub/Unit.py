import csv
import logging
import os
import typing as tp
from dataclasses import dataclass
from datetime import datetime as dt
from uuid import uuid4

import yaml

from . import _external_io_operations as external_io
from ._Employee import Employee
from ._Passport import Passport
from ._Types import Config, ProductData


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
        self.uuid: str = uuid or self._generate_uuid()
        self.internal_id: str = self._get_internal_id()
        self.employee: tp.Optional[Employee] = None
        self.product_data: tp.Optional[ProductData] = self._get_product_data()
        self.passport = Passport(self)
        self._keyword = ""
        self._config = config
        self.workplace_data: str = ""
        self.product_type: str = ""
        self._unit_biography: tp.List[ProductionStage] = []

    @property
    def employee_name(self) -> str:
        return self.employee.name

    @property
    def current_operation(self) -> tp.Union[ProductionStage, None]:
        if self._unit_biography:
            return self._unit_biography[-1]
        else:
            return None

    @current_operation.setter
    def current_operation(self, current_operation: ProductionStage) -> None:
        self._unit_biography.append(current_operation)

    @staticmethod
    def _generate_uuid() -> str:
        return uuid4().hex

    def _get_internal_id(self) -> str:
        """get own internal id using own uuid"""
        ids_dict = self._load_internal_ids()

        if not len(ids_dict):
            self._save_internal_id(self.uuid, 1)
            return "1"

        internal_id = list(ids_dict.values())[-1] + 1
        self._save_internal_id(self.uuid, internal_id)

        return str(internal_id)

    def _get_product_data(self) -> ProductData:
        filename = f"unit-passports/unit-passport-{self.uuid}.yaml"
        if os.path.exists(filename):
            with open(filename, "r") as f:
                content = f.read()
                product_data: ProductData = yaml.load(content, Loader=yaml.FullLoader)

            logging.info(f"Loaded up product data for a unit with UUID {self.uuid}")
        else:
            logging.info(f"Passport for the unit with uuid {self.uuid} not found. New one was generated.")
            product_data = {}

        return product_data

    @staticmethod
    def _load_internal_ids(path: str = "config/internal_ids") -> tp.Dict[str, int]:
        """Loads internal ids matching table, returns dict in format {uuid: internal_id}"""
        internal_ids = {}

        with open(path, "r", newline="") as f:
            data = csv.reader(f, delimiter=";")
            for uuid, id_ in data:
                internal_ids[uuid] = id_

        return internal_ids

    @staticmethod
    def _save_internal_id(uuid: str, internal_id: int, path: str = "config/internal_ids"):
        """Saves internal id matching table, returns dict in format {uuid: internal_id}"""
        with open(path, "w", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([uuid, internal_id])

        logging.debug(f"Saved {uuid[:6]}:{internal_id} to matching table")

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
            employee_name=self.employee_name,
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

    def upload(self) -> None:

        # upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics
        gateway = external_io.ExternalIoGateway(self._config)
        gateway.send(self.passport.filename, self._keyword)
