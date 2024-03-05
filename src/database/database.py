from dataclasses import asdict
from typing import Any

import pydantic
from loguru import logger
from pymongo import MongoClient
from pymongo.database import Database

from ._db_utils import _get_database_client, _get_unit_dict_data
from ..feecc_workbench.config import CONFIG
from ..feecc_workbench.Employee import Employee
from ..feecc_workbench.exceptions import EmployeeNotFoundError, UnitNotFoundError
from .models import ProductionSchema
from ..feecc_workbench.ProductionStage import ProductionStage
from ..feecc_workbench.Types import BulkWriteTask, Document
from ..feecc_workbench.Unit import Unit
from ..feecc_workbench.unit_utils import UnitStatus
from ..feecc_workbench.utils import time_execution


class _BaseMongoDbWrapper:
    """handles interactions with MongoDB database"""

    @logger.catch
    def __init__(self) -> None:
        logger.info("Trying to connect to MongoDB")

        self._client: MongoClient = _get_database_client(CONFIG.db.mongo_connection_uri)
        self._database: Database = self._client[CONFIG.db.mongo_db_name]

        logger.info("Successfully connected to MongoDB")

    def close_connection(self) -> None:
        self._client.close()
        logger.info("MongoDB connection closed")

    def insert(self, collection: str, entity: dict[str, Any]) -> str:
        """Inserts the entity in the specified collection."""
        return self._database[collection].insert_one(entity).inserted_id

    def read(self, collection: str, filters: dict[str, Any] = {}) -> list[dict[str, Any]]:
        """Returns the list of all items if filter is not specified. Otherwise returns the whole collection."""
        return list(self._database[collection].find(filters))

    def update(self, collection: str, update: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
        """Updates the specified document's fields."""
        return self._database[collection].find_one_and_update(filter=filters, update=update)
    
    def delete(self, collection: str, filters: dict[str, Any]) -> int:
        """Deletes filtered results and returns it's number."""
        return self._database[collection].delete_one(filter=filters).deleted_count

    # def _bulk_push_production_stages(self, production_stages: list[ProductionStage]) -> None:
    #     tasks: list[BulkWriteTask] = []

    #     for stage in production_stages:
    #         stage_dict = asdict(stage)
    #         del stage_dict["is_in_db"]

    #         if stage.is_in_db:
    #             task: BulkWriteTask = UpdateOne({"id": stage.id}, {"$set": stage_dict})
    #         else:
    #             task = InsertOne(stage_dict)
    #             stage.is_in_db = True

    #         tasks.append(task)

    #     result = self._prod_stage_collection.bulk_write(tasks)
    #     logger.debug(f"Bulk write operation result: {result.bulk_api_result}")

    # @time_execution
    # def push_unit(self, unit: Unit, include_components: bool = True) -> None:
    #     """Upload or update data about the unit into the DB"""
    #     if unit.components_units and include_components:
    #         for component in unit.components_units:
    #             self.push_unit(component)

    #     self._bulk_push_production_stages(unit.biography)
    #     unit_dict = _get_unit_dict_data(unit)

    #     if unit.is_in_db:
    #         self._unit_collection.find_one_and_update({"uuid": unit.uuid}, {"$set": unit_dict})
    #     else:
    #         self._unit_collection.insert_one(unit_dict)

    # @time_execution
    # def unit_update_single_field(self, unit_internal_id: str, field_name: str, field_val: Any) -> None:
    #     self._unit_collection.find_one_and_update(
    #         {"internal_id": unit_internal_id}, {"$set": {field_name: field_val}}
    #     )
    #     logger.debug(f"Unit {unit_internal_id} field '{field_name}' has been set to '{field_val}'")

    # def _get_unit_from_raw_db_data(self, unit_dict: Document) -> Unit:
    #     # get nested component units
    #     components_internal_ids = unit_dict.get("components_internal_ids", [])
    #     components_units = []

    #     for component_internal_id in components_internal_ids:
    #         component_unit = self.get_unit_by_internal_id(component_internal_id)
    #         components_units.append(component_unit)

    #     # get biography objects instead of dicts
    #     stage_dicts = unit_dict.get("prod_stage_dicts", [])
    #     biography = []

    #     for stage_dict in stage_dicts:
    #         production_stage = ProductionStage(**stage_dict)
    #         production_stage.is_in_db = True
    #         biography.append(production_stage)

    #     # construct a Unit object from the document data
    #     return Unit(
    #         schema=self.get_schema_by_id(unit_dict["schema_id"]),
    #         uuid=unit_dict.get("uuid"),
    #         internal_id=unit_dict.get("internal_id"),
    #         is_in_db=True,
    #         biography=biography or None,
    #         components_units=components_units or None,
    #         featured_in_int_id=unit_dict.get("featured_in_int_id"),
    #         passport_ipfs_cid=unit_dict.get("passport_ipfs_cid"),
    #         txn_hash=unit_dict.get("txn_hash"),
    #         serial_number=unit_dict.get("serial_number"),
    #         creation_time=unit_dict.get("creation_time"),
    #         status=unit_dict.get("status", None),
    #     )

    # @time_execution
    # def get_unit_ids_and_names_by_status(self, status: UnitStatus) -> list[dict[str, str]]:
    #     pipeline = [  # noqa: CCR001,ECE001
    #         {"$match": {"status": status.value}},
    #         {
    #             "$lookup": {
    #                 "from": "productionSchemas",
    #                 "let": {"schema_id": "$schema_id"},
    #                 "pipeline": [
    #                     {"$match": {"$expr": {"$eq": ["$schema_id", "$$schema_id"]}}},
    #                     {"$project": {"_id": 0, "unit_name": 1}},
    #                 ],
    #                 "as": "unit_name",
    #             }
    #         },
    #         {"$unwind": {"path": "$unit_name"}},
    #         {"$project": {"_id": 0, "unit_name": 1, "internal_id": 1}},
    #     ]
    #     result: list[Document] = self._unit_collection.aggregate(pipeline).to_list(length=None)

    #     return [
    #         {
    #             "internal_id": entry["internal_id"],
    #             "unit_name": entry["unit_name"]["unit_name"],
    #         }
    #         for entry in result
    #     ]

    # @time_execution
    # def get_employee_by_card_id(self, card_id: str) -> Employee:
    #     """find the employee with the provided RFID card id"""
    #     employee_data: Document | None = self._employee_collection.find_one({"rfid_card_id": card_id}, {"_id": 0})

    #     if employee_data is None:
    #         message = f"No employee with card ID {card_id}"
    #         logger.error(message)
    #         raise EmployeeNotFoundError(message)

    #     return Employee(**employee_data)

    # @time_execution
    # def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
    #     pipeline = [  # noqa: CCR001,ECE001
    #         {"$match": {"internal_id": unit_internal_id}},
    #         {
    #             "$lookup": {
    #                 "from": "productionStagesData",
    #                 "let": {"parent_uuid": "$uuid"},
    #                 "pipeline": [
    #                     {"$match": {"$expr": {"$eq": ["$parent_unit_uuid", "$$parent_uuid"]}}},
    #                     {"$project": {"_id": 0}},
    #                     {"$sort": {"number": 1}},
    #                 ],
    #                 "as": "prod_stage_dicts",
    #             }
    #         },
    #         {"$project": {"_id": 0}},
    #     ]

    #     try:
    #         result: list[Document] = self._unit_collection.aggregate(pipeline).to_list(length=1)
    #     except Exception as e:
    #         logger.error(e)
    #         raise e

    #     if not result:
    #         message = f"Unit with internal id {unit_internal_id} not found"
    #         logger.warning(message)
    #         raise UnitNotFoundError(message)

    #     unit_dict: Document = result[0]

    #     return self._get_unit_from_raw_db_data(unit_dict)

    # def get_all_schemas(self) -> list[ProductionSchema]:
    #     """get all production schemas"""
    #     schema_data = self._schemas_collection.find({}, {"_id": 0}).to_list(length=None)
    #     return [pydantic.parse_obj_as(ProductionSchema, schema) for schema in schema_data]

    # @time_execution
    # def get_schema_by_id(self, schema_id: str) -> ProductionSchema:
    #     """get the specified production schema"""
    #     target_schema = self._schemas_collection.find_one({"schema_id": schema_id}, {"_id": 0})

    #     if target_schema is None:
    #         raise ValueError(f"Schema {schema_id} not found")

    #     return pydantic.parse_obj_as(ProductionSchema, target_schema)


base_mongodb_wrapper = _BaseMongoDbWrapper()
