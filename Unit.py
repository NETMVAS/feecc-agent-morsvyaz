import logging
import os
import typing as tp
from datetime import datetime as dt
from uuid import uuid4

import yaml

from Employee import Employee
from Passport import Passport
from Types import Config, ProductData
from modules import external_io_operations


class Unit:
    """Unit class corresponds to one uniquely identifiable physical production unit"""

    def __init__(self, config: Config, associated_employee: Employee, uuid: str = "") -> None:
        self.uuid: str = uuid or self._generate_uuid()
        self.internal_id: str = ""
        self.employee: Employee = associated_employee
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

    def end_session(self) -> None:
        """wrap up the session when video recording stops an save video data as well as session end timestamp"""

        self.session_end_time = dt.now().strftime("%d-%m-%Y %H:%M:%S")

    def upload(self) -> None:

        # upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics
        gateway = external_io_operations.ExternalIoGateway(self._config)
        gateway.send(self.passport.filename, self._keyword)
