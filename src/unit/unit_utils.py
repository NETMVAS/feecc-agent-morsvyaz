from __future__ import annotations

import enum
from datetime import datetime as dt
from typing import TYPE_CHECKING
from pydantic import BaseModel
from uuid import uuid4

from src.database.models import ProductionSchema, AdditionalDetail
from src.prod_stage.ProductionStage import ProductionStage
from src.feecc_workbench._label_generation import Barcode
from src.employee.Employee import Employee
from src.prod_schema.prod_schema_wrapper import ProdSchemaWrapper
from src.unit.unit_wrapper import UnitWrapper

if TYPE_CHECKING:
    from .Unit import Unit


def biography_factory(schema_id: str, parent_unit_uuid: str) -> list[ProductionStage]:
    operation_stages = []
    production_schema = ProdSchemaWrapper.get_schema_by_id(schema_id)
    if production_schema.production_stages is not None:
        for i, stage in enumerate(production_schema.production_stages):
            operation = ProductionStage(
                name=stage.name,
                parent_unit_uuid=parent_unit_uuid,
                number=i,
                schema_stage_id=stage.stage_id,
            )
            operation_stages.append(operation)

    return operation_stages


class UnitStatus(enum.Enum):
    """supported Unit status descriptors"""

    production = "production"
    built = "built"
    revision = "revision"
    finalized = "finalized"


def _get_unit_list(unit_: Unit) -> list[Unit]:
    """list all the units in the component tree"""
    units_tree = [unit_]
    if unit_.components_ids:
        components_units = UnitWrapper.get_components_units(unit_.components_ids)
    for component_ in components_units:
        nested = _get_unit_list(component_)
        units_tree.extend(nested)
    return units_tree


def get_first_unit_matching_status(unit: Unit, *target_statuses: UnitStatus) -> Unit:
    """get first unit matching having target status in unit tree"""
    for component in _get_unit_list(unit):
        if component.status in target_statuses:
            return component
    raise AssertionError("Unit features no components that are in allowed states")


class Unit(BaseModel):
    status: UnitStatus
    schema_id: str  # The id of the schema used in production
    uuid: str = uuid4().hex
    operation_name: str  # The name of the operation (simple, complex etc)
    barcode: Barcode = Barcode(str(int(uuid, 16))[:12])
    internal_id: str = str(barcode.barcode.get_fullcode())
    certificate_ipfs_cid: str | None = None
    certificate_ipfs_link: str | None = None
    txn_hash: str | None = None
    serial_number: str | None = None
    components_ids: list[str] = []
    featured_in_int_id: str | None = None
    employee: Employee | None = None
    operation_stages: list[ProductionStage] = []
    is_in_db: bool = False
    creation_time: dt.datetime = dt.datetime.now()
    detail: AdditionalDetail | None = None
    _component_slots: dict[str, Unit | None] | None = None

    def model_post_init(self, __context: enum.Any) -> None:
        # if not self.schema_id.production_stages and self.status is UnitStatus.production:
        #     self.status = UnitStatus.built

        # if self.components_units:
        #     slots: dict[str, Unit | None] = {u.schema_id: u for u in self.components_units}
        #     assert all(
        #         k in (self.schema.required_components_schema_ids or []) for k in slots
        #     ), "Provided components are not a part of the unit schema"
        # else:
        #     slots = {schema_id: None for schema_id in (self.schema.required_components_schema_ids or [])}

        # self._component_slots: dict[str, Unit | None] = slots

        if not self.operation_stages:
            self.operation_stages = biography_factory(self.schema_id, self.uuid)

        return super().model_post_init(__context)
