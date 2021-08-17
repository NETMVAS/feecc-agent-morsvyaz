from __future__ import annotations

import os
import typing as tp

import yaml
from loguru import logger

from ._external_io_operations import File

if tp.TYPE_CHECKING:
    from .Unit import ProductionStage, Unit


class Passport:
    """handles form validation and unit passport issuing"""

    def __init__(self, unit: Unit) -> None:
        self._unit: Unit = unit
        path = f"unit-passports/unit-passport-{self._unit.uuid}.yaml"
        self.file: File = File(path)
        logger.info(f"Passport {self._unit.uuid} initialized for unit with int. ID {self._unit.internal_id}")

    @staticmethod
    def _construct_stage_dict(prod_stage: ProductionStage, ipfs_gateway: str) -> tp.Dict[str, tp.Any]:
        stage: tp.Dict[str, tp.Any] = {
            "Наименование": prod_stage.name,
            "Код сотрудника": prod_stage.employee_name,
            "Время начала": prod_stage.session_start_time,
            "Время окончания": prod_stage.session_end_time,
        }

        if prod_stage.video_hashes is not None:
            video_links: tp.List[str] = [ipfs_gateway + hash_ for hash_ in prod_stage.video_hashes]
            stage["Видеозаписи процесса сборки в IPFS"] = video_links

        if prod_stage.additional_info:
            stage["Дополнительная информация"] = prod_stage.additional_info

        return stage

    def _construct_passport_dict(self, gateway: str) -> tp.Dict[str, tp.Any]:
        """
        form a nested dictionary containing all the unit
        data to dump it into a passport in a human friendly form
        """
        biography: tp.List[tp.Dict[str, tp.Any]] = [
            self._construct_stage_dict(prod_stage, gateway) for prod_stage in self._unit.unit_biography
        ]
        passport_dict = {
            "Уникальный номер паспорта изделия": self._unit.uuid,
            "Модель изделия": self._unit.model,
            "Этапы производства": biography,
        }

        logger.debug(f"Constructed passport dict for unit with id {self._unit.internal_id}:\n{passport_dict}")
        return passport_dict

    def save(self, ipfs_gateway: str = "https://gateway.ipfs.io/ipfs/") -> None:
        """makes a unit passport and dumps it in a form of a YAML file"""
        passport_dict = self._construct_passport_dict(ipfs_gateway)

        # make directory if it is missing
        if not os.path.isdir("unit-passports"):
            os.mkdir("unit-passports")

        with open(self.file.path, "w") as passport_file:
            yaml.dump(passport_dict, passport_file, allow_unicode=True, sort_keys=False)

        logger.info(f"Unit passport with UUID {self._unit.uuid} has been dumped successfully")
