import datetime as dt
import pathlib
from typing import Any

import yaml
from loguru import logger

from src.prod_stage.ProductionStage import ProductionStage
from src.unit.unit_utils import Unit
from src.unit.unit_wrapper import UnitWrapper
from src.feecc_workbench.translation import translation


def _construct_stage_dict(prod_stage: ProductionStage) -> dict[str, Any]:
    stage: dict[str, Any] = {
        translation("BuildName"): prod_stage.name,
        translation("BuildEmployee"): prod_stage.employee_name,
        translation("BuildStartTime"): prod_stage.session_start_time,
        translation("BuildEndTime"): prod_stage.session_end_time,
    }

    if prod_stage.video_hashes is not None:
        stage[translation("BuildVideoHashes")] = [
            f"https://gateway.ipfs.io/ipfs/{cid}" for cid in prod_stage.video_hashes
        ]

    if prod_stage.additional_info:
        stage[translation("BuildAdditionalInfo")] = prod_stage.additional_info

    return stage


def _get_total_assembly_time(unit: Unit) -> dt.timedelta:
    """Calculate total assembly time of the unit and all its components recursively"""
    own_time: dt.timedelta = unit.total_assembly_time
    if unit.components_ids:
        components_units = UnitWrapper.get_components_units(unit.components_ids)

    for component in components_units:
        component_time = _get_total_assembly_time(component)
        own_time += component_time

    return own_time


def _get_certificate_dict(unit: Unit) -> dict[str, Any]:
    """
    form a nested dictionary containing all the unit
    data to dump it into a human friendly certificate
    """
    certificate_dict: dict[str, Any] = {
        translation("UnitID"): unit.uuid,
        translation("UnitName"): unit.model_name,
    }

    try:
        certificate_dict[translation("UnitTotalAssemblyTime")] = str(unit.total_assembly_time)
    except Exception as e:
        logger.error(str(e))

    if unit.biography:
        certificate_dict[translation("UnitBiography")] = [_construct_stage_dict(stage) for stage in unit.biography]

    if unit.components_ids:
        components_units = UnitWrapper.get_components_units(unit.components_ids)
        certificate_dict[translation("UnitComponents")] = [_get_certificate_dict(c) for c in components_units]
        certificate_dict[translation("UnitTotalAssemblyTimeComponents")] = str(_get_total_assembly_time(unit))

    if unit.serial_number:
        certificate_dict[translation("UnitSerialNumber")] = unit.serial_number

    if unit.detail:
        certificate_dict[translation("BuildDetails")] = unit.detail

    return certificate_dict


def _save_certificate(unit: Unit, certificate_dict: dict[str, Any], path: str) -> None:
    """makes a unit certificate and dumps it in a form of a YAML file"""
    dir_ = pathlib.Path("unit-certificates")
    if not dir_.is_dir():
        dir_.mkdir()
    certificate_file = pathlib.Path(path)
    with certificate_file.open("w") as f:
        yaml.dump(certificate_dict, f, allow_unicode=True, sort_keys=False)
    logger.info(f"Unit certificate with UUID {unit.uuid} has been dumped successfully")


@logger.catch(reraise=True)
async def construct_unit_certificate(unit: Unit) -> pathlib.Path:
    """construct own certificate, dump it as .yaml file and return a path to it"""
    certificate = _get_certificate_dict(unit)
    path = f"unit-certificates/unit-certificate-{unit.uuid}.yaml"
    _save_certificate(unit, certificate, path)
    return pathlib.Path(path)
