import enum

from .models import ProductionSchema
from .ProductionStage import ProductionStage


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
    approved = "approved"
    finalized = "finalized"
