import typing as tp
from dataclasses import asdict

import pydantic
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from yarl import URL

from .Employee import Employee
from .ProductionStage import ProductionStage
from .Singleton import SingletonMeta
from .Types import Document
from .Unit import Unit
from ._db_utils import _get_database_client, _get_unit_dict_data
from .config import CONFIG
from .exceptions import EmployeeNotFoundError, UnitNotFoundError
from .models import ProductionSchema
from .unit_utils import UnitStatus


class MongoDbWrapper(metaclass=SingletonMeta):
    """handles interactions with MongoDB database"""

    @logger.catch
    def __init__(self) -> None:
        logger.info("Trying to connect to MongoDB")

        uri = CONFIG.db.mongo_connection_uri

        self._client: AsyncIOMotorClient = _get_database_client(uri)
        db_name: str = URL(uri).path.lstrip("/")
        self._database: AsyncIOMotorDatabase = self._client[db_name]

        # collections
        self._employee_collection: AsyncIOMotorCollection = self._database["employeeData"]
        self._unit_collection: AsyncIOMotorCollection = self._database["unitData"]
        self._prod_stage_collection: AsyncIOMotorCollection = self._database["productionStagesData"]
        self._schemas_collection: AsyncIOMotorCollection = self._database["productionSchemas"]

        logger.info("Successfully connected to MongoDB")

    @staticmethod
    async def _upload_dict(document: Document, collection_: AsyncIOMotorCollection) -> None:
        """insert a document into specified collection"""
        logger.debug(f"Uploading document {document} to {collection_.name}")
        await collection_.insert_one(document)

    async def _upload_dataclass(self, dataclass: tp.Any, collection_: AsyncIOMotorCollection) -> None:
        """
        convert an arbitrary dataclass to dictionary and insert it
        into the desired collection in the database
        """
        await self._upload_dict(asdict(dataclass), collection_)

    @staticmethod
    async def _find_item(key: str, value: str, collection_: AsyncIOMotorCollection) -> tp.Optional[Document]:
        """
        finds one element in the specified collection, which has
        specified key matching specified value
        """
        return await collection_.find_one({key: value}, {"_id": 0})  # type: ignore

    @staticmethod
    async def _find_many(key: str, value: str, collection_: AsyncIOMotorCollection) -> tp.List[Document]:
        """
        finds all elements in the specified collection, which have
        specified key matching specified value
        """
        return await collection_.find({key: value}, {"_id": 0}).to_list(length=None)  # type: ignore

    @staticmethod
    async def _get_all_items_in_collection(collection_: AsyncIOMotorCollection) -> tp.List[Document]:
        """get all documents in the provided collection"""
        return await collection_.find({}, {"_id": 0}).to_list(length=None)  # type: ignore

    @staticmethod
    async def _update_document(
        key: str, value: str, new_document: Document, collection_: AsyncIOMotorCollection
    ) -> None:
        """
        finds matching document in the specified collection, and replaces it's data
        with what is provided in the new_document argument
        """
        logger.debug(f"Updating key {key} with value {value}")
        await collection_.find_one_and_update({key: value}, {"$set": new_document})

    async def update_production_stage(self, updated_production_stage: ProductionStage) -> None:
        """update data about the production stage in the DB"""
        stage_dict: Document = asdict(updated_production_stage)
        stage_id: str = updated_production_stage.id
        await self._update_document("id", stage_id, stage_dict, self._prod_stage_collection)

    async def update_unit(self, unit: Unit, include_keys: tp.Optional[tp.List[str]] = None) -> None:
        """update data about the unit in the DB"""
        for stage in unit.biography:
            if stage.is_in_db:
                await self.update_production_stage(stage)
            else:
                await self.upload_production_stage(stage)

        unit_dict = _get_unit_dict_data(unit)

        if include_keys is not None:
            unit_dict = {key: unit_dict.get(key) for key in include_keys}

        await self._update_document("uuid", unit.uuid, unit_dict, self._unit_collection)

    async def _get_unit_from_raw_db_data(self, unit_dict: Document) -> Unit:
        return Unit(
            schema=await self.get_schema_by_id(unit_dict["schema_id"]),
            uuid=unit_dict.get("uuid", None),
            internal_id=unit_dict.get("internal_id", None),
            is_in_db=unit_dict.get("is_in_db", None),
            biography=[ProductionStage(**stage) for stage in unit_dict.get("prod_stage_dicts", [])] or None,
            components_units=[
                await self.get_unit_by_internal_id(id_) for id_ in unit_dict.get("components_internal_ids", [])
            ]
            or None,
            featured_in_int_id=unit_dict.get("featured_in_int_id", None),
            passport_short_url=unit_dict.get("passport_short_url", None),
            passport_ipfs_cid=unit_dict.get("passport_ipfs_cid", None),
            txn_hash=unit_dict.get("txn_hash", None),
            serial_number=unit_dict.get("serial_number", None),
            creation_time=unit_dict.get("creation_time", None),
            status=unit_dict.get("status", None),
        )

    async def get_all_units_by_status(self, status: UnitStatus) -> tp.List[Unit]:
        return [
            await self._get_unit_from_raw_db_data(entry)
            for entry in await self._find_many("status", status.value, self._unit_collection)
        ]

    async def upload_unit(self, unit: Unit) -> None:
        """
        convert a unit instance into a dictionary suitable for future reassembly while
        converting nested structures and uploading them
        """
        for component in unit.components_units:
            await self.upload_unit(component)

        if unit.is_in_db:
            return
        else:
            unit.is_in_db = True

        unit_dict = _get_unit_dict_data(unit)

        # upload nested dataclasses
        for stage in unit.biography:
            await self.upload_production_stage(stage)

        await self._upload_dict(unit_dict, self._unit_collection)

    async def upload_production_stage(self, production_stage: ProductionStage) -> None:
        if production_stage.is_in_db:
            return

        production_stage.is_in_db = True
        await self._upload_dataclass(production_stage, self._prod_stage_collection)

    async def get_employee_by_card_id(self, card_id: str) -> Employee:
        """find the employee with the provided RFID card id"""
        employee_data: tp.Optional[Document] = await self._find_item("rfid_card_id", card_id, self._employee_collection)

        if employee_data is None:
            message = f"No employee with card ID {card_id}"
            logger.error(message)
            raise EmployeeNotFoundError(message)

        return Employee(**employee_data)

    async def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
        pipeline = [
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
            result: tp.List[Document] = await self._unit_collection.aggregate(pipeline).to_list(length=1)
        except Exception as E:
            logger.error(E)
            raise E

        if not result:
            message = f"Unit with {unit_internal_id=} not found"
            logger.warning(message)
            raise UnitNotFoundError(message)

        unit_dict: Document = result[0]

        return await self._get_unit_from_raw_db_data(unit_dict)

    async def get_all_schemas(self) -> tp.List[ProductionSchema]:
        """get all production schemas"""
        schema_data = await self._get_all_items_in_collection(self._schemas_collection)
        return [pydantic.parse_obj_as(ProductionSchema, schema) for schema in schema_data]

    async def get_schema_by_id(self, schema_id: str) -> ProductionSchema:
        """get the specified production schema"""
        target_schema = await self._find_item("schema_id", schema_id, self._schemas_collection)

        if target_schema is None:
            raise ValueError(f"Schema {schema_id} not found")

        return pydantic.parse_obj_as(ProductionSchema, target_schema)
