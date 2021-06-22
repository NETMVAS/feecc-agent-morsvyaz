import csv
import logging
import os
import typing as tp
from datetime import datetime as dt
from uuid import uuid4

import yaml

from modules.Employee import Employee
from modules.Passport import Passport
from modules.Types import Config, ProductData
from modules import external_io_operations


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
        self.session_start_time: str = ""
        self.session_end_time: str = ""
        self.product_type: str = ""
        self.additional_info: tp.Dict[str, str] = {}

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

    def _load_internal_ids(self, path: str = "config/internal_ids") -> tp.Dict[str, int]:
        """Loads internal ids matching table, returns dict in format {uuid: internal_id}"""
        internal_ids = {}

        with open(path, "r", newline="") as f:
            data = csv.reader(f, delimiter=";")
            for uuid, id in data:
                internal_ids[uuid] = id

        return internal_ids

    def _save_internal_id(self, uuid: str, internal_id: int, path: str = "config/internal_ids"):
        """Saves internal id matching table, returns dict in format {uuid: internal_id}"""
        with open(path, "w", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([uuid, internal_id])

        logging.debug(f"Saved {uuid[:6]}:{internal_id} to matching table")

    def end_session(self) -> None:
        """wrap up the session when video recording stops an save video data as well as session end timestamp"""

        self.session_end_time = dt.now().strftime("%d-%m-%Y %H:%M:%S")

    def upload(self) -> None:

        # upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics
        gateway = external_io_operations.ExternalIoGateway(self._config)
        gateway.send(self.passport.filename, self._keyword)
