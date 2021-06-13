import hashlib
import logging
import os

import yaml

from Unit import Unit


class Passport:
    """handles form validation and unit passport issuing"""

    def __init__(self, unit: Unit) -> None:
        self._unit = unit
        self.filename: str = f"unit-passports/unit-passport-{self._unit.uuid}.yaml"

        logging.info(f"Passport {self._unit.uuid} initialized by employee with ID {self._unit.employee.id}")

    @property
    def product_data(self):
        return self._unit.product_data

    def _encode_employee(self) -> str:
        """
        returns encoded employee name to put into the passport
        
        since unit passport will be published to IPFS, employee name is replaced with
        "employee passport code" - an SHA256 checksum of a string, which is a space-separated
        combination of employee's ID, name and position. since this data is unique for every
        employee, it is safe to assume, that collision is impossible.
        """

        employee_passport_string: str = " ".join(self._unit.employee.employee_db_entry)
        employee_passport_string_encoded: bytes = employee_passport_string.encode()
        employee_passport_code: str = hashlib.sha256(employee_passport_string_encoded).hexdigest()
        return employee_passport_code

    def save(self) -> None:
        """makes a unit passport and dumps it in a form of a YAML file"""

        employee_passport_code = self._encode_employee
        passport_dict = self._unit.product_data
        passport_dict["Employee name"] = employee_passport_code

        # make directory if it is missing
        if not os.path.isdir("unit-passports"):
            os.mkdir("unit-passports")

        with open(self.filename, "w") as passport_file:
            yaml.dump(passport_dict, passport_file, allow_unicode=True, sort_keys=False)

        logging.info(f"Unit passport with UUID {self._unit.uuid} has been dumped successfully")
