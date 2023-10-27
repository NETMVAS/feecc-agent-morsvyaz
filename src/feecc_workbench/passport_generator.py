import datetime as dt
import pathlib
from typing import Any

import yaml
from loguru import logger

from .ProductionStage import ProductionStage
from .Unit import Unit
from .translation import translation


def _construct_stage_dict(prod_stage: ProductionStage) -> dict[str, Any]:
    stage: dict[str, Any] = {
        translation('Name'): prod_stage.name,
        translation('Employee'): prod_stage.employee_name,
        translation('StartTime'): prod_stage.session_start_time,
        translation('EndTime'): prod_stage.session_end_time,
    }

    if prod_stage.video_hashes is not None:
        stage[translation('VideoBuild')] = [
            f"https://gateway.ipfs.io/ipfs/{cid}" for cid in prod_stage.video_hashes
        ]

    if prod_stage.additional_info:
        stage[translation('Information')] = prod_stage.additional_info

    return stage


def _get_total_assembly_time(unit: Unit) -> dt.timedelta:
    """Calculate total assembly time of the unit and all its components recursively"""
    own_time: dt.timedelta = unit.total_assembly_time

    for component in unit.components_units:
        component_time = _get_total_assembly_time(component)
        own_time += component_time

    return own_time


def _get_passport_dict(unit: Unit) -> dict[str, Any]:
    """
    form a nested dictionary containing all the unit
    data to dump it into a human friendly passport
    """
    passport_dict: dict[str, Any] = {
        translation('ProductID'): unit.uuid,
        translation('ProductModel'): unit.model_name,
    }

    try:
        passport_dict[translation('BuildTime')] = str(unit.total_assembly_time)
    except Exception as e:
        logger.error(str(e))

    if unit.biography:
        passport_dict[translation('ProdStage')] = [_construct_stage_dict(stage) for stage in unit.biography]

    if unit.components_units:
        passport_dict[translation('Components')] = [_get_passport_dict(c) for c in unit.components_units]
        passport_dict[translation('BuildTimeComponents')] = str(_get_total_assembly_time(unit))

    if unit.serial_number:
        passport_dict[translation('SerialNumber')] = unit.serial_number

    return passport_dict


def _save_passport(unit: Unit, passport_dict: dict[str, Any], path: str) -> None:
    """makes a unit passport and dumps it in a form of a YAML file"""
    dir_ = pathlib.Path("unit-passports")
    if not dir_.is_dir():
        dir_.mkdir()
    passport_file = pathlib.Path(path)
    with passport_file.open("w") as f:
        yaml.dump(passport_dict, f, allow_unicode=True, sort_keys=False)
    logger.info(f"Unit passport with UUID {unit.uuid} has been dumped successfully")


@logger.catch(reraise=True)
async def construct_unit_passport(unit: Unit) -> pathlib.Path:
    """construct own passport, dump it as .yaml file and return a path to it"""
    passport = _get_passport_dict(unit)
    path = f"unit-passports/unit-passport-{unit.uuid}.yaml"
    _save_passport(unit, passport, path)
    return pathlib.Path(path)
