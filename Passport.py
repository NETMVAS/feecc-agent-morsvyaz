import csv
import hashlib
import logging
import os
import typing as tp
import uuid
from datetime import datetime as dt

import yaml

import modules.external_io_operations as external_io
from Employee import Employee

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="agent.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)


class Passports:
    """Base class for Passport contains different methods to work with them"""
    instances = []

    def __init__(self) -> None:
        self.passports_db_path: str = "issued_passports.csv"
        self.passports_matching_table: str = "matching_table.csv"
        self.active_passports: tp.Optional[tp.Dict[int, str]] = None

        self.final_state: str = "Упаковка"

    def _remove_active_passport(self, passport_id: int) -> None:
        """
        Method that removes the passport from the list of active

        Args:
            passport_id (int):
        """
        active_passports = self._parse_active_passports()

        try:
            active_passports.pop(passport_id)
        except KeyError:
            logging.error(f"Value {passport_id} not found in active passports")
            return None

        logging.info(f"Passport {passport_id} removed from active passports list")

        self._write_active_passports(active_passports, rewrite=True)

        self.active_passports = active_passports

    def _write_active_passports(self, active_passports: tp.Dict[int, str], rewrite: bool = False) -> None:
        """
        Method that writes multiple active passports into csv file

        Args:
            active_passports (dict): dict in format of {id: hash, ..., idN: hashN}

        Returns:

        """
        option = "w" if rewrite else "a"

        logging.info(f"Active passports dumped into {self.passports_matching_table} (Rewrite={rewrite})")

        for key, value in active_passports.values():
            with open(self.passports_matching_table, option, newline="") as f:
                csv_writer = csv.writer(f, delimiter=";")
                csv_writer.writerows([int(key), value])

    def _parse_active_passports(self) -> tp.Dict[int, str]:
        """
        Method takes data about passports from a CSV table and returns them as a dict

        Returns:
            Dict in format {id: hash}
        """
        passports = {}

        with open(self.passports_matching_table, "r", newline="") as f:
            data = csv.reader(f, delimiter=";")
            for _id, _hash in data:
                passports[_id] = _hash

        return passports

    def match_passport_id_with_hash(self, passport_id: str) -> tp.Optional[str]:
        """
        Method matches passport id and its hash from the database

        Args:
            passport_id: numeric value of passport id

        Returns:
            None or Passport hash (str)
        """
        try:
            entry = self._parse_active_passports()[passport_id]
            logging.info(f"id {passport_id} matched with {entry}")
            return entry
        except KeyError:
            logging.error(f"Unable to match id {passport_id} with any passport")
            return None

    def append_to_yaml(self, passports_dict_list: tp.List[tp.Dict[str, tp.Dict[str, tp.Any]]]) -> None:
        """
        Method allows you to add values to an already created YAML file

        Args:
            passports_dict_list (list of dicts): Stores a list of dictionaries, with data about the product (passports)
        """
        for passport in passports_dict_list:
            work_state = list(passport.keys())[0]
            try:
                yaml_name = f"unit-passports/unit-passport-{work_state}.yaml"
                with open(yaml_name, "a") as f:
                    yaml.dump(
                        f,
                        passport
                    )
            except KeyError:
                logging.error("Can't find key 'Этап производства' in given dict")
            except IOError as E:
                logging.critical(f"File unit-passport-{work_state}.yaml unavailable. {E}")

            if work_state == self.final_state:
                self._remove_active_passport(passport[work_state]["Уникальный номер паспорта изделия"])
                break

        return None


class Passport(Passports):
    """handles form validation and unit passport issuing"""

    def __init__(self, rfid_card_id: str, config: tp.Dict[str, tp.Dict[str, tp.Any]]) -> None:
        # passport id and employee data based on employee ID
        super().__init__()
        self.passport_id: str = uuid.uuid4().hex
        self.passport_ipfs_hash: str = ""
        self.config = config
        self._employee_id: str = rfid_card_id
        self._employee_db_entry: tp.List[str] = Employee.find_in_db(rfid_card_id)

        # refuse service if employee unknown
        if not self._employee_db_entry:
            logging.error(f"Employee with ID {self._employee_id} is not in the DB, service refused")
            raise ValueError

        # refuse service if employee database has wrong format
        valid_len = 3
        if not len(self._employee_db_entry) == 3:
            logging.critical(f"Employee DB has to have at least {valid_len} columns")
            return

        # log success
        logging.info(f"Passport {self.passport_id} initialized by employee with ID {self._employee_id}")

        # passport field
        self.employee_name: str = self._employee_db_entry[1]
        self.employee_position: str = self._employee_db_entry[2]
        self.session_start_time: str = ""
        self.session_end_time: str = ""
        self.workplace_data: str = ""
        self.product_type: str = ""
        self.additional_info: tp.Dict[str, str] = {}
        self.video_ipfs_hash: tp.List[str] = []
        self.filename: str = ""

        # append class instance to base class' all instances list
        self.instances.append(self)

    def submit_form(self, form: tp.Dict[str, tp.Any]) -> bool:
        """
        accepts a JSON form, validates it and assigns
        form contents to instance's properties if form is valid (returns True).
        If validation failed - returns False and does nothing.
        """

        # validate form
        reference_form = {
            "session_start_time": "01-01-1970 00:00:00",
            "product_type": "Perseverance Mars rover",
            "production_stage": "Final assembly",
            "additional_info":
                {
                    "field_1": "Sample text",
                    "field_2": "Sample text",
                    "field_3": "Sample text"
                }
        }

        form_keys = list(form.keys())
        form_keys.sort()
        reference_form_keys = list(reference_form.keys())
        reference_form_keys.sort()

        if form_keys == reference_form_keys:
            self.session_start_time = form["session_start_time"]
            self.product_type = form["product_type"]
            self.additional_info = form["additional_info"]
            self.workplace_data = form["production_stage"]

            return True

        else:
            logging.error(f"Error validating form data. Key mismatch with reference model")
            return False

    def export_yaml(self) -> None:
        """makes a unit passport and dumps it in a form of a YAML file"""

        # since unit passport will be published to IPFS, employee name is replaced with
        # "employee passport code" - an SHA256 checksum of a string, which is a space-separated
        # combination of employee's ID, name and position. since this data is unique for every
        # employee, it is safe to assume, that collision is impossible.

        # generate employee passport code
        employee_passport_string = " ".join(self._employee_db_entry)
        employee_passport_string_encoded = employee_passport_string.encode()
        employee_passport_code = hashlib.sha256(employee_passport_string_encoded).hexdigest()

        logging.debug(f"self.session_start_time = {self.session_start_time}")

        passport_dict = {
            self.workplace_data: {
                "Уникальный номер паспорта изделия": self.passport_id,
                "Модель изделия": self.product_type,
                "Комплектация": self.additional_info,
                "Начало сборки": self.session_start_time,
                "Окончание сборки": self.session_end_time,
                "Изготовил": employee_passport_code,
                "Видеозаписи процесса сборки в IPFS": self.video_ipfs_hash
            }
        }

        logging.debug(f"raw passport_dict = {passport_dict}")

        # make directory if it is missing
        if not os.path.isdir("unit-passports"):
            os.mkdir("unit-passports")

        # save into a file and save the filename
        self.filename = f"unit-passports/unit-passport-{self.passport_id}.yaml"
        with open(self.filename, "w") as passport_file:
            yaml.dump(
                passport_dict,
                passport_file,
                allow_unicode=True,
                sort_keys=False
            )

        logging.info(f"Unit passport with UUID {self.passport_id} has been dumped successfully")

        # upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics
        self.passport_ipfs_hash = external_io.send(
            filename=self.filename,
            config=self.config
        )

        # also save passport IPFS hash locally in case Robonomics datalog is not written
        with open(self.passports_db_path, "a") as file:
            file.writelines(
                f"{self.passport_id};{self.passport_ipfs_hash}\n"
            )

    def end_session(self, ipfs_hash: tp.List[str]) -> None:
        """wrap up the session when video recording stops an save video data as well as session end timestamp"""

        for _hash in ipfs_hash:
            self.video_ipfs_hash.append(_hash)

        self.session_end_time = dt.now().strftime("%d-%m-%Y %H:%M:%S")
