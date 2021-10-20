from __future__ import annotations

import os
import typing as tp
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime as dt
from uuid import uuid4

import yaml
from loguru import logger

from .Employee import Employee
from .IO_gateway import generate_qr_code, post_to_datalog, print_image, publish_file
from .Types import AdditionalInfo
from ._Barcode import Barcode
from ._image_generation import create_seal_tag
from .config import config
from .models import ProductionSchema

if tp.TYPE_CHECKING:
    from .database import MongoDbWrapper


def timestamp() -> str:
    """generate formatted timestamp for the invocation moment"""
    return dt.now().strftime("%d-%m-%Y %H:%M:%S")


@dataclass
class ProductionStage:
    name: str
    employee_name: str
    parent_unit_uuid: str
    session_start_time: str = field(default_factory=timestamp)
    session_end_time: tp.Optional[str] = None
    video_hashes: tp.Optional[tp.List[str]] = None
    additional_info: tp.Optional[AdditionalInfo] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    is_in_db: bool = False
    creation_time: dt = field(default_factory=lambda: dt.utcnow())


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
        passport_short_url: tp.Optional[str] = None,
    ) -> None:
        self.schema: ProductionSchema = schema
        self.uuid: str = uuid or uuid4().hex
        self.barcode: Barcode = Barcode(str(int(self.uuid, 16))[:12])
        self.internal_id: str = internal_id or str(self.barcode.barcode.get_fullcode())
        self.passport_short_url: tp.Optional[str] = passport_short_url
        self.components_units: tp.List[Unit] = components_units or []
        self.employee: tp.Optional[Employee] = None
        self.biography: tp.List[ProductionStage] = biography or []
        self.is_in_db: bool = is_in_db or False

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

    @tp.no_type_check
    def assigned_components(self) -> tp.Optional[tp.Dict[str, tp.Optional[str]]]:
        """get a mapping for all the currently assigned components VS the desired components"""
        assigned_components = {component.model: component.internal_id for component in self.components_units}

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
                self.components_units.append(component)
                logger.info(f"Component {component.model} has been assigned to a composite Unit {self.model}")
            else:
                message = f"Component {component.model} is already assigned to a composite Unit {self.model}"
                logger.error(message)
                raise ValueError(message)

        else:
            message = f"Cannot assign component {component.model} to {self.model} as it's not a component of it"
            logger.error(message)
            raise ValueError(message)

    def dict_data(self) -> tp.Dict[str, tp.Union[str, bool, None, tp.List[str]]]:
        return {
            "schema_id": self.schema.schema_id,
            "uuid": self.uuid,
            "internal_id": self.internal_id,
            "is_in_db": self.is_in_db,
            "passport_short_url": self.passport_short_url,
            "components_internal_ids": self.components_internal_ids,
        }

    @property
    def current_operation(self) -> tp.Optional[ProductionStage]:
        return self.biography[-1] if self.biography else None

    @current_operation.setter
    def current_operation(self, current_operation: ProductionStage) -> None:
        self.biography.append(current_operation)

    def start_session(
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

    async def end_session(
        self,
        database: MongoDbWrapper,
        video_hashes: tp.Optional[tp.List[str]] = None,
        additional_info: tp.Optional[AdditionalInfo] = None,
    ) -> None:
        """
        wrap up the session when video recording stops and save video data
        as well as session end timestamp
        """
        if self.current_operation is None:
            raise ValueError("No ongoing operations found")

        logger.info(f"Ending production stage {self.current_operation.name}")
        operation = deepcopy(self.current_operation)
        operation.session_end_time = timestamp()

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
        await database.update_unit(self)

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

    def get_passport_dict(self) -> tp.Dict[str, tp.Any]:
        """
        form a nested dictionary containing all the unit
        data to dump it into a in a human friendly passport
        """
        passport_dict = {
            "Уникальный номер паспорта изделия": self.uuid,
            "Модель изделия": self.model,
            "Этапы производства": [self._construct_stage_dict(prod_stage) for prod_stage in self.biography],
        }

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

    @logger.catch
    async def upload(self, database: MongoDbWrapper, rfid_card_id: str) -> None:
        """upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics"""
        passport = self.get_passport_dict()
        path = f"unit-passports/unit-passport-{self.uuid}.yaml"
        self._save_passport(passport, path)

        if config.print_qr.enable:
            short_url, qrcode_path = generate_qr_code()
            await print_image(
                qrcode_path, rfid_card_id, annotation=f"{self.model} (ID: {self.internal_id}). {short_url}"
            )

            if config.print_security_tag.enable:
                seal_tag_img: str = create_seal_tag()
                await print_image(seal_tag_img, rfid_card_id)

        res = await publish_file(path, rfid_card_id)

        if config.robonomics_network.enable_datalog and res is not None:
            cid: str = res[0]
            post_to_datalog(cid)

        if self.is_in_db:
            await database.update_unit(self)
        else:
            await database.upload_unit(self)
