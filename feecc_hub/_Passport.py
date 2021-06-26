import hashlib
import logging
import os
import typing as tp

import yaml


class Passport:
    """handles form validation and unit passport issuing"""

    def __init__(self, unit) -> None:
        self._unit = unit
        self.filename: str = f"unit-passports/unit-passport-{self._unit.uuid}.yaml"
        logging.info(
            f"Passport {self._unit.uuid} initialized for unit with int. ID {self._unit.internal_id}"
        )

    def _construct_passport_dict(self) -> tp.Dict[str, tp.Any]:
        """
        form a nested dictionary containing all the unit
        data to dump it into a passport in a human friendly form
        """

        biography: tp.List[tp.Dict[str, tp.Any]] = []

        for prod_stage in self._unit.unit_biography:
            stage = {
                "Этап производства": prod_stage.production_stage_name,
                "Сотрудник": prod_stage.employee_name,
                "Время начала": prod_stage.session_start_time,
                "Время окончания": prod_stage.session_end_time,
            }

            if prod_stage.video_hashes is not None:
                stage["Видеозаписи процесса сборки в IPFS"] = prod_stage.video_hashes

            if prod_stage.additional_info is not None:
                stage["Дополнительная информация"] = prod_stage.additional_info

            biography.append(stage)

        passport_dict = {
            "Уникальный номер паспорта изделия": self._unit.uuid,
            "Модель изделия:": self._unit.model,
            "Этапы производства": biography,
        }

        logging.debug(
            f"Constructed passport dict for the unit with int. id {self._unit.internal_id}:\n{passport_dict}"
        )
        return passport_dict

    def encode_employee(self) -> tp.Optional[str]:
        """
        returns encoded employee name to put into the passport

        since unit passport will be published to IPFS, employee name is replaced with
        "employee passport code" - an SHA256 checksum of a string, which is a space-separated
        combination of employee's ID, name and position. since this data is unique for every
        employee, it is safe to assume, that collision is impossible.
        """

        if self._unit.employee is not None:
            employee_passport_string: str = " ".join(self._unit.employee.employee_db_entry)
            employee_passport_string_encoded: bytes = employee_passport_string.encode()
            employee_passport_code: str = hashlib.sha256(
                employee_passport_string_encoded
            ).hexdigest()
            return employee_passport_code
        else:
            return None

    def save(self) -> None:
        """makes a unit passport and dumps it in a form of a YAML file"""

        passport_dict = self._construct_passport_dict()

        # make directory if it is missing
        if not os.path.isdir("unit-passports"):
            os.mkdir("unit-passports")

        with open(self.filename, "w") as passport_file:
            yaml.dump(passport_dict, passport_file, allow_unicode=True, sort_keys=False)

        logging.info(f"Unit passport with UUID {self._unit.uuid} has been dumped successfully")
