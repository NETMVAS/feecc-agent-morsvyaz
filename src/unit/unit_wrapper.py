from loguru import logger
from typing import Any

from src.database.database import base_mongodb_wrapper
from src.database._db_utils import _get_unit_dict_data
from src.prod_stage.ProductionStage import ProductionStage
from src.prod_stage.prod_stage_wrapper import prod_stage_wrapper
from src.feecc_workbench.Types import Document
from src.feecc_workbench.utils import time_execution
from src.feecc_workbench.exceptions import UnitNotFoundError
from src.prod_schema.prod_schema_wrapper import prod_schema_wrapper
from .Unit import Unit
from .unit_utils import UnitStatus



class UnitWrapper:
    collection = "unitData"

    @time_execution
    def push_unit(self, unit: Unit, include_components: bool = True) -> None:
        """Upload or update data about the unit into the DB"""
        if unit.components_units and include_components:
            for component in unit.components_units:
                self.push_unit(component)

        prod_stage_wrapper._bulk_push_production_stages(unit.biography)
        unit_dict = _get_unit_dict_data(unit)

        if unit.is_in_db:
            filters = {"uuid": unit.uuid}
            update = {"$set": unit_dict}
            base_mongodb_wrapper.update(self.collection, update, filters)
        else:
            base_mongodb_wrapper.insert(self.collection, unit_dict)

    @time_execution
    def unit_update_single_field(self, unit_internal_id: str, field_name: str, field_val: Any) -> None:
        filters = {"internal_id": unit_internal_id}
        update = {"$set": {field_name: field_val}}
        base_mongodb_wrapper.update(self.collection, update, filters)
        logger.debug(f"Unit {unit_internal_id} field '{field_name}' has been set to '{field_val}'")

    @time_execution
    def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
        pipeline = [  # noqa: CCR001,ECE001
            {"$match": {"internal_id": unit_internal_id}},
            {
                "$lookup": {
                    "from": "productionStagesData",
                    "let": {"parent_uuid": "$uuid"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$parent_unit_uuid", "$$parent_uuid"]}}},
                        {"$project": {"_id": 0}},
                        {"$sort": {"number": 1}},
                    ],
                    "as": "prod_stage_dicts",
                }
            },
            {"$project": {"_id": 0}},
        ]

        try:
            result: list[Document] = base_mongodb_wrapper.aggregate(self.collection, pipeline)
        except Exception as e:
            logger.error(e)
            raise e

        if not result:
            message = f"Unit with internal id {unit_internal_id} not found"
            logger.warning(message)
            raise UnitNotFoundError(message)

        unit_dict: Document = result[0]

        return self._get_unit_from_raw_db_data(unit_dict)

    def _get_unit_from_raw_db_data(self, unit_dict: Document) -> Unit:
        # get nested component units
        components_internal_ids = unit_dict.get("components_internal_ids", [])
        components_units = []

        for component_internal_id in components_internal_ids:
            component_unit = self.get_unit_by_internal_id(component_internal_id)
            components_units.append(component_unit)

        # get biography objects instead of dicts
        stage_dicts = unit_dict.get("prod_stage_dicts", [])
        biography = []

        for stage_dict in stage_dicts:
            production_stage = ProductionStage(**stage_dict)
            production_stage.is_in_db = True
            biography.append(production_stage)

        # construct a Unit object from the document data
        return Unit(
            schema=prod_schema_wrapper.get_schema_by_id(unit_dict["schema_id"]),
            uuid=unit_dict.get("uuid"),
            internal_id=unit_dict.get("internal_id"),
            is_in_db=True,
            biography=biography or None,
            components_units=components_units or None,
            featured_in_int_id=unit_dict.get("featured_in_int_id"),
            passport_ipfs_cid=unit_dict.get("passport_ipfs_cid"),
            txn_hash=unit_dict.get("txn_hash"),
            serial_number=unit_dict.get("serial_number"),
            creation_time=unit_dict.get("creation_time"),
            status=unit_dict.get("status", None),
        )

    @time_execution
    def get_unit_ids_and_names_by_status(self, status: UnitStatus) -> list[dict[str, str]]:
        pipeline = [  # noqa: CCR001,ECE001
            {"$match": {"status": status.value}},
            {
                "$lookup": {
                    "from": "productionSchemas",
                    "let": {"schema_id": "$schema_id"},
                    "pipeline": [
                        {"$match": {"$expr": {"$eq": ["$schema_id", "$$schema_id"]}}},
                        {"$project": {"_id": 0, "unit_name": 1}},
                    ],
                    "as": "unit_name",
                }
            },
            {"$unwind": {"path": "$unit_name"}},
            {"$project": {"_id": 0, "unit_name": 1, "internal_id": 1}},
        ]
        result: list[Document] = base_mongodb_wrapper.aggregate(self.collection, pipeline)

        return [
            {
                "internal_id": entry["internal_id"],
                "unit_name": entry["unit_name"]["unit_name"],
            }
            for entry in result
        ]


unit_wrapper = UnitWrapper()
