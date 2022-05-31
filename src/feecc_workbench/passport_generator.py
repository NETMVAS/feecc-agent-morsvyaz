import os
from typing import Any

import yaml
from loguru import logger

from .ProductionStage import ProductionStage
from .Unit import Unit


def _construct_stage_dict(prod_stage: ProductionStage) -> dict[str, Any]:
    stage: dict[str, Any] = {
        "Наименование": prod_stage.name,
        "Код сотрудника": prod_stage.employee_name,
        "Время начала": prod_stage.session_start_time,
        "Время окончания": prod_stage.session_end_time,
    }

    if prod_stage.video_hashes is not None:
        stage["Видеозаписи процесса сборки в IPFS"] = [
            "https://gateway.ipfs.io/ipfs/" + cid for cid in prod_stage.video_hashes
        ]

    if prod_stage.additional_info:
        stage["Дополнительная информация"] = prod_stage.additional_info

    return stage


def _get_passport_dict(unit: Unit) -> dict[str, Any]:
    """
    form a nested dictionary containing all the unit
    data to dump it into a human friendly passport
    """
    passport_dict: dict[str, Any] = {
        "Уникальный номер паспорта изделия": unit.uuid,
        "Модель изделия": unit.model_name,
    }

    try:
        passport_dict["Общая продолжительность сборки"] = str(unit.total_assembly_time)
    except Exception as e:
        logger.error(str(e))

    if unit.biography:
        passport_dict["Этапы производства"] = [_construct_stage_dict(stage) for stage in unit.biography]

    if unit.components_units:
        passport_dict["Компоненты в составе изделия"] = [_get_passport_dict(c) for c in unit.components_units]

    if unit.serial_number:
        passport_dict["Серийный номер изделия"] = unit.serial_number

    return passport_dict


def _save_passport(unit: Unit, passport_dict: dict[str, Any], path: str) -> None:
    """makes a unit passport and dumps it in a form of a YAML file"""
    if not os.path.isdir("unit-passports"):
        os.mkdir("unit-passports")
    with open(path, "w") as passport_file:
        yaml.dump(passport_dict, passport_file, allow_unicode=True, sort_keys=False)
    logger.info(f"Unit passport with UUID {unit.uuid} has been dumped successfully")


@logger.catch(reraise=True)
async def construct_unit_passport(unit: Unit) -> str:
    """construct own passport, dump it as .yaml file and return a path to it"""
    passport = _get_passport_dict(unit)
    path = f"unit-passports/unit-passport-{unit.uuid}.yaml"
    _save_passport(unit, passport, path)
    return path
