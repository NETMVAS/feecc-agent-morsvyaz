from dataclasses import asdict
from typing import Any

import pydantic
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import InsertOne, UpdateOne

from ._db_utils import _get_database_client, _get_unit_dict_data
from .config import CONFIG
from .Employee import Employee
from .exceptions import EmployeeNotFoundError, UnitNotFoundError
from .models import ProductionSchema
from .ProductionStage import ProductionStage
from .Singleton import SingletonMeta
from .Types import BulkWriteTask, Document
from .Unit import Unit
from .unit_utils import UnitStatus
from .utils import async_time_execution


class MongoDbWrapper(metaclass=SingletonMeta):
    """handles interactions with MongoDB database"""

    @logger.catch
    def __init__(self) -> None:
        logger.info("Trying to connect to MongoDB")

        self._client: AsyncIOMotorClient = _get_database_client(CONFIG.db.mongo_connection_uri)
        db_name: str = CONFIG.db.mongo_db_name
        self._database: AsyncIOMotorDatabase = self._client[db_name]

        # collections
        self._employee_collection: AsyncIOMotorCollection = self._database.employeeData
        self._unit_collection: AsyncIOMotorCollection = self._database.unitData
        self._prod_stage_collection: AsyncIOMotorCollection = self._database.productionStagesData
        self._schemas_collection: AsyncIOMotorCollection = self._database.productionSchemas

        logger.info("Successfully connected to MongoDB")

    def close_connection(self) -> None:
        self._client.close()
        logger.info("MongoDB connection closed")

    async def _bulk_push_production_stages(self, production_stages: list[ProductionStage]) -> None:
        tasks: list[BulkWriteTask] = []

        for stage in production_stages:
            stage_dict = asdict(stage)
            del stage_dict["is_in_db"]

            if stage.is_in_db:
                task: BulkWriteTask = UpdateOne({"id": stage.id}, {"$set": stage_dict})
            else:
                task = InsertOne(stage_dict)
                stage.is_in_db = True

            tasks.append(task)

        result = await self._prod_stage_collection.bulk_write(tasks)
        logger.debug(f"Bulk write operation result: {result.bulk_api_result}")

    @async_time_execution
    async def push_unit(self, unit: Unit, include_components: bool = True) -> None:
        """Upload or update data about the unit into the DB"""
        if unit.components_units and include_components:
            for component in unit.components_units:
                await self.push_unit(component)

        await self._bulk_push_production_stages(unit.biography)
        unit_dict = _get_unit_dict_data(unit)

        if unit.is_in_db:
            await self._unit_collection.find_one_and_update({"uuid": unit.uuid}, {"$set": unit_dict})
        else:
            await self._unit_collection.insert_one(unit_dict)

    @async_time_execution
    async def unit_update_single_field(self, unit_internal_id: str, field_name: str, field_val: Any) -> None:
        await self._unit_collection.find_one_and_update(
            {"internal_id": unit_internal_id}, {"$set": {field_name: field_val}}
        )
        logger.debug(f"Unit {unit_internal_id} field '{field_name}' has been set to '{field_val}'")

    async def _get_unit_from_raw_db_data(self, unit_dict: Document) -> Unit:
        # get nested component units
        components_internal_ids = unit_dict.get("components_internal_ids", [])
        components_units = []

        for component_internal_id in components_internal_ids:
            component_unit = await self.get_unit_by_internal_id(component_internal_id)
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
            schema=await self.get_schema_by_id(unit_dict["schema_id"]),
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

    @async_time_execution
    async def get_unit_ids_and_names_by_status(self, status: UnitStatus) -> list[dict[str, str]]:
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
        result: list[Document] = await self._unit_collection.aggregate(pipeline).to_list(length=None)

        return [
            {
                "internal_id": entry["internal_id"],
                "unit_name": entry["unit_name"]["unit_name"],
            }
            for entry in result
        ]

    @async_time_execution
    async def get_employee_by_card_id(self, card_id: str) -> Employee:
        """find the employee with the provided RFID card id"""
        employee_data: Document | None = await self._employee_collection.find_one({"rfid_card_id": card_id}, {"_id": 0})

        if employee_data is None:
            message = f"No employee with card ID {card_id}"
            logger.error(message)
            raise EmployeeNotFoundError(message)

        return Employee(**employee_data)

    @async_time_execution
    async def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
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
            result: list[Document] = await self._unit_collection.aggregate(pipeline).to_list(length=1)
        except Exception as e:
            logger.error(e)
            raise e

        if not result:
            message = f"Unit with internal id {unit_internal_id} not found"
            logger.warning(message)
            raise UnitNotFoundError(message)

        unit_dict: Document = result[0]

        return await self._get_unit_from_raw_db_data(unit_dict)

    @async_time_execution
    async def get_all_schemas(self) -> list[ProductionSchema]:
        """get all production schemas"""
        schema_data = await self._schemas_collection.find({}, {"_id": 0}).to_list(length=None)
        return [pydantic.parse_obj_as(ProductionSchema, schema) for schema in schema_data]

    @async_time_execution
    async def get_schema_by_id(self, schema_id: str) -> ProductionSchema:
        """get the specified production schema"""
        target_schema = await self._schemas_collection.find_one({"schema_id": schema_id}, {"_id": 0})

        if target_schema is None:
            raise ValueError(f"Schema {schema_id} not found")

        return pydantic.parse_obj_as(ProductionSchema, target_schema)
