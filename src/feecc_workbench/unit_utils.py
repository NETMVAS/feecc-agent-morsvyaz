from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from .models import ProductionSchema
from .ProductionStage import ProductionStage

if TYPE_CHECKING:
    from .Unit import Unit


def biography_factory(production_schema: ProductionSchema, parent_unit_uuid: str) -> list[ProductionStage]:
    biography = []

    if production_schema.production_stages is not None:
        for i, stage in enumerate(production_schema.production_stages):
            operation = ProductionStage(
                name=stage.name,
                parent_unit_uuid=parent_unit_uuid,
                number=i,
                schema_stage_id=stage.stage_id,
            )
            biography.append(operation)

    return biography


class UnitStatus(enum.Enum):
    """supported Unit status descriptors"""

    production = "production"
    built = "built"
    revision = "revision"
    finalized = "finalized"


def _get_unit_list(unit_: Unit) -> list[Unit]:
    """list all the units in the component tree"""
    units_tree = [unit_]
    for component_ in unit_.components_units:
        nested = _get_unit_list(component_)
        units_tree.extend(nested)
    return units_tree


def get_first_unit_matching_status(unit: Unit, *target_statuses: UnitStatus) -> Unit:
    """get first unit matching having target status in unit tree"""
    for component in _get_unit_list(unit):
        if component.status in target_statuses:
            return component
    raise AssertionError("Unit features no components that are in allowed states")
