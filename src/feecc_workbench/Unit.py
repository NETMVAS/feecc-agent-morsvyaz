from __future__ import annotations

import datetime as dt
import os
import typing as tp
from copy import deepcopy
from dataclasses import dataclass, field
from functools import reduce
from operator import add
from uuid import uuid4

import yaml
from loguru import logger

from .Employee import Employee
from .Types import AdditionalInfo
from ._Barcode import Barcode
from .models import ProductionSchema

TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M:%S"


def timestamp() -> str:
    """generate formatted timestamp for the invocation moment"""
    return dt.datetime.now().strftime(TIMESTAMP_FORMAT)


@dataclass
class ProductionStage:
    name: str
    employee_name: str
    parent_unit_uuid: str
    session_start_time: str = field(default_factory=timestamp)
    session_end_time: tp.Optional[str] = None
    ended_prematurely: bool = False
    video_hashes: tp.Optional[tp.List[str]] = None
    additional_info: tp.Optional[AdditionalInfo] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    is_in_db: bool = False
    creation_time: dt.datetime = field(default_factory=lambda: dt.datetime.utcnow())


class Unit:
    """Unit class corresponds to one uniquely identifiable physical production unit"""

    def __init__(
        self,
        schema: ProductionSchema,
        uuid: tp.Optional[str] = None,
        internal_id: tp.Optional[str] = None,
        is_in_db: tp.Optional[bool] = None,
        biography: tp.Optional[tp.List[ProductionStage]] = None,
        components_units: tp.Optional[tp.List[Unit]] = None,
        featured_in_int_id: tp.Optional[str] = None,
        passport_short_url: tp.Optional[str] = None,
        passport_ipfs_cid: tp.Optional[str] = None,
        creation_time: tp.Optional[dt.datetime] = None,
    ) -> None:
        self.schema: ProductionSchema = schema
        self.uuid: str = uuid or uuid4().hex
        self.barcode: Barcode = Barcode(str(int(self.uuid, 16))[:12])
        self.internal_id: str = internal_id or str(self.barcode.barcode.get_fullcode())
        self.passport_short_url: tp.Optional[str] = passport_short_url
        self.passport_ipfs_cid: tp.Optional[str] = passport_ipfs_cid
        self.components_units: tp.List[Unit] = components_units or []
        self.featured_in_int_id: tp.Optional[str] = featured_in_int_id
        self.employee: tp.Optional[Employee] = None
        self.biography: tp.List[ProductionStage] = biography or []
        self.is_in_db: bool = is_in_db or False
        self.creation_time: dt.datetime = creation_time or dt.datetime.utcnow()

    @property
    def components_schema_ids(self) -> tp.List[str]:
        return self.schema.required_components_schema_ids or []

    @property
    def components_internal_ids(self) -> tp.List[str]:
        return [c.internal_id for c in self.components_units]

    @property
    def model(self) -> str:
        return self.schema.unit_name

    @property
    def components_filled(self) -> bool:
        if self.components_schema_ids:
            if not self.components_units:
                return False

            return len(self.components_schema_ids) == len(self.components_units)

        return True

    @property
    def current_operation(self) -> tp.Optional[ProductionStage]:
        return self.biography[-1] if self.biography else None

    @current_operation.setter
    def current_operation(self, current_operation: ProductionStage) -> None:
        self.biography.append(current_operation)

    @property
    def is_completed(self) -> bool:
        if self.schema.production_stages is None:
            return True
        return len(self.schema.production_stages) == len(self.biography)

    @property
    def total_assembly_time(self) -> dt.timedelta:
        """calculate total time spent during all production stages"""

        def stage_len(stage: ProductionStage) -> dt.timedelta:
            start_time: dt.datetime = dt.datetime.strptime(stage.session_start_time, TIMESTAMP_FORMAT)
            end_time: dt.datetime = (
                dt.datetime.strptime(stage.session_end_time, TIMESTAMP_FORMAT)
                if stage.session_end_time is not None
                else dt.datetime.now()
            )
            return end_time - start_time

        return reduce(add, (stage_len(stage) for stage in self.biography)) if self.biography else dt.timedelta(0)

    @tp.no_type_check
    def assigned_components(self) -> tp.Optional[tp.Dict[str, tp.Optional[str]]]:
        """get a mapping for all the currently assigned components VS the desired components"""
        assigned_components = {component.schema.schema_id: component.internal_id for component in self.components_units}

        for component_name in self.components_schema_ids:
            if component_name not in assigned_components:
                assigned_components[component_name] = None

        return assigned_components or None

    def assign_component(self, component: Unit) -> None:
        """acquire one of the composite unit's components"""
        if self.components_filled:
            logger.error(f"Unit {self.model} component requirements have already been satisfied")

        elif component.schema.schema_id in self.components_schema_ids:
            if component.schema.schema_id not in (c.schema.schema_id for c in self.components_units):
                if not component.is_completed:
                    raise ValueError(f"Component {component.model} assembly is not completed")

                elif component.featured_in_int_id is not None:
                    raise ValueError(
                        f"Component {component.model} has already been used in unit {component.featured_in_int_id}"
                    )

                else:
                    self.components_units.append(component)
                    component.featured_in_int_id = self.internal_id
                    logger.info(f"Component {component.model} has been assigned to a composite Unit {self.model}")

            else:
                message = f"Component {component.model} is already assigned to a composite Unit {self.model}"
                logger.error(message)
                raise ValueError(message)

        else:
            message = f"Cannot assign component {component.model} to {self.model} as it's not a component of it"
            logger.error(message)
            raise ValueError(message)

    def dict_data(self) -> tp.Dict[str, tp.Union[str, bool, None, tp.List[str], dt.datetime]]:
        return {
            "schema_id": self.schema.schema_id,
            "uuid": self.uuid,
            "internal_id": self.internal_id,
            "is_in_db": self.is_in_db,
            "passport_short_url": self.passport_short_url,
            "passport_ipfs_cid": self.passport_ipfs_cid,
            "components_internal_ids": self.components_internal_ids,
            "featured_in_int_id": self.featured_in_int_id,
            "creation_time": self.creation_time,
        }

    def start_operation(
        self,
        employee: Employee,
        production_stage_name: str,
        additional_info: tp.Optional[AdditionalInfo] = None,
    ) -> None:  # sourcery skip: simplify-fstring-formatting
        """begin the provided operation and save data about it"""
        logger.info(f"Starting production stage {production_stage_name} for unit with int_id {self.internal_id}")
        logger.debug(f"additional info for {self.internal_id} {additional_info or 'is empty'}")

        operation = ProductionStage(
            name=production_stage_name,
            employee_name=employee.get_passport_code(),
            parent_unit_uuid=self.uuid,
            additional_info=additional_info,
        )

        self.current_operation = operation

        logger.debug(f"Started production stage {production_stage_name} for {str(operation)}")

    async def end_operation(
        self,
        video_hashes: tp.Optional[tp.List[str]] = None,
        additional_info: tp.Optional[AdditionalInfo] = None,
        premature: bool = False,
        override_timestamp: tp.Optional[str] = None,
    ) -> None:
        """
        wrap up the session when video recording stops and save video data
        as well as session end timestamp
        """
        if self.current_operation is None:
            raise ValueError("No ongoing operations found")

        logger.info(f"Ending production stage {self.current_operation.name}")
        operation = deepcopy(self.current_operation)
        operation.session_end_time = override_timestamp or timestamp()

        if premature:
            operation.name += " (неокончен.)"
            operation.ended_prematurely = True

        if video_hashes:
            operation.video_hashes = video_hashes

        if additional_info:
            if operation.additional_info is not None:
                operation.additional_info = {
                    **operation.additional_info,
                    **additional_info,
                }
            else:
                operation.additional_info = additional_info

        self.biography[-1] = operation
        logger.debug(f"Unit biography stage count is now {len(self.biography)}")
        self.employee = None

    @staticmethod
    def _construct_stage_dict(prod_stage: ProductionStage) -> tp.Dict[str, tp.Any]:
        stage: tp.Dict[str, tp.Any] = {
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

    def get_passport_dict(self) -> tp.Dict[str, tp.Any]:
        """
        form a nested dictionary containing all the unit
        data to dump it into a in a human friendly passport
        """
        passport_dict: tp.Dict[str, tp.Any] = {
            "Уникальный номер паспорта изделия": self.uuid,
            "Модель изделия": self.model,
        }

        try:
            passport_dict["Общая продолжительность сборки"] = str(self.total_assembly_time)
        except Exception as e:
            logger.error(str(e))

        if self.biography:
            passport_dict["Этапы производства"] = [self._construct_stage_dict(stage) for stage in self.biography]

        if self.components_units:
            passport_dict["Компоненты в составе изделия"] = [c.get_passport_dict() for c in self.components_units]

        return passport_dict

    def _save_passport(self, passport_dict: tp.Dict[str, tp.Any], path: str) -> None:
        """makes a unit passport and dumps it in a form of a YAML file"""
        if not os.path.isdir("unit-passports"):
            os.mkdir("unit-passports")
        with open(path, "w") as passport_file:
            yaml.dump(passport_dict, passport_file, allow_unicode=True, sort_keys=False)
        logger.info(f"Unit passport with UUID {self.uuid} has been dumped successfully")

    @logger.catch(reraise=True)
    async def construct_unit_passport(self) -> str:
        """construct own passport, dump it as .yaml file and return a path to it"""
        passport = self.get_passport_dict()
        path = f"unit-passports/unit-passport-{self.uuid}.yaml"
        self._save_passport(passport, path)
        return path
