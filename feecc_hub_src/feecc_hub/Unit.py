from __future__ import annotations

import typing as tp
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime as dt
from uuid import uuid4

from loguru import logger

from .config import config
from .Employee import Employee
from .Types import AdditionalInfo
from ._Barcode import Barcode
from ._Passport import Passport
from ._image_generation import create_seal_tag

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
        model: str,
        uuid: tp.Optional[str] = None,
        internal_id: tp.Optional[str] = None,
        is_in_db: tp.Optional[bool] = None,
        biography: tp.Optional[tp.List[ProductionStage]] = None,
        passport_short_url: tp.Optional[str] = None,
    ) -> None:
        self.model: str = model
        self.uuid: str = uuid or uuid4().hex
        self.barcode: Barcode = Barcode(str(int(self.uuid, 16))[:12])
        self.internal_id: str = internal_id or str(self.barcode.barcode.get_fullcode())
        self.passport_short_url: tp.Optional[str] = passport_short_url

        self.employee: tp.Optional[Employee] = None
        self.biography: tp.List[ProductionStage] = biography or []
        self.is_in_db: bool = is_in_db or False

        if config.print_barcode.enable and not self.is_in_db:
            Printer().print_image(self.barcode.filename, self.model)

    def dict_data(self) -> tp.Dict[str, tp.Union[str, bool, None]]:
        return {
            "model": self.model,
            "uuid": self.uuid,
            "internal_id": self.internal_id,
            "is_in_db": self.is_in_db,
            "passport_short_url": self.passport_short_url,
        }

    @property
    def current_operation(self) -> tp.Optional[ProductionStage]:
        return self.biography[-1] if self.biography else None

    @current_operation.setter
    def current_operation(self, current_operation: ProductionStage) -> None:
        self.biography.append(current_operation)

    def start_session(
        self,
        production_stage_name: str,
        employee_code_name: str,
        additional_info: tp.Optional[AdditionalInfo] = None,
    ) -> None:
        """begin the provided operation and save data about it"""
        logger.info(f"Starting production stage {production_stage_name} for unit with int_id {self.internal_id}")
        logger.debug(f"additional info for {self.internal_id} {additional_info or 'is empty'}")

        operation = ProductionStage(
            name=production_stage_name,
            employee_name=employee_code_name,
            parent_unit_uuid=self.uuid,
            additional_info=additional_info,
        )

        self.current_operation = operation

        logger.debug(f"Started production stage {production_stage_name} for {str(operation)}")

    def end_session(
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
        database.update_unit(self)

    def upload(self, database: MongoDbWrapper) -> None:
        """upload passport file into IPFS and pin it to Pinata, publish hash to Robonomics"""
        passport = Passport(self)
        passport.save()

        if config.print_qr.enable:
            qrcode: str = passport.generate_qr_code()
            # Printer().print_image(
            #     qrcode, annotation=f"{self.model} (ID: {self.internal_id}). {passport.short_url}"
            # )

            if config.print_security_tag.enable:
                seal_tag_img: str = create_seal_tag()
                # Printer().print_image(seal_tag_img)

        # ExternalIoGateway().send(self._associated_passport)
        if self.is_in_db:
            database.update_unit(self)
        else:
            database.upload_unit(self)
