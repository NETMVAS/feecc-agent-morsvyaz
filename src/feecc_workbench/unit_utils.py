import enum
import typing as tp

from .ProductionStage import ProductionStage
from .models import ProductionSchema


def biography_factory(production_schema: ProductionSchema, parent_unit_uuid: str) -> tp.List[ProductionStage]:
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
    approved = "approved"
    finalized = "finalized"
