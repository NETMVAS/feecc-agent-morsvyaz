from __future__ import annotations

import os
import typing as tp

import yaml
from loguru import logger

from .IO_gateway import File

if tp.TYPE_CHECKING:
    from .Unit import ProductionStage, Unit


class Passport(File):
    """handles form validation and unit passport issuing"""

    def __init__(self, unit: Unit) -> None:
        path = f"unit-passports/unit-passport-{unit.uuid}.yaml"
        super().__init__(path, short_url=unit.passport_short_url)
        self._unit: Unit = unit

    @staticmethod
    def _construct_stage_dict(prod_stage: ProductionStage) -> tp.Dict[str, tp.Any]:
        stage: tp.Dict[str, tp.Any] = {
            "Наименование": prod_stage.name,
            "Код сотрудника": prod_stage.employee_name,
            "Время начала": prod_stage.session_start_time,
            "Время окончания": prod_stage.session_end_time,
        }

        if prod_stage.video_hashes is not None:
            stage["Видеозаписи процесса сборки в IPFS"] = prod_stage.video_hashes

        if prod_stage.additional_info:
            stage["Дополнительная информация"] = prod_stage.additional_info

        return stage

    def _construct_passport_dict(self) -> tp.Dict[str, tp.Any]:
        """
        form a nested dictionary containing all the unit
        data to dump it into a in a human friendly passport
        """
        return {
            "Уникальный номер паспорта изделия": self._unit.uuid,
            "Модель изделия": self._unit.model,
            "Этапы производства": [self._construct_stage_dict(prod_stage) for prod_stage in self._unit.biography],
        }

    def save(self) -> None:
        """makes a unit passport and dumps it in a form of a YAML file"""
        passport_dict = self._construct_passport_dict()

        if not os.path.isdir("unit-passports"):
            os.mkdir("unit-passports")

        with open(self.path, "w") as passport_file:
            yaml.dump(passport_dict, passport_file, allow_unicode=True, sort_keys=False)

        logger.info(f"Unit passport with UUID {self._unit.uuid} has been dumped successfully")
