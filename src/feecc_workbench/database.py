import os
import sys
import typing as tp
from dataclasses import asdict

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from .Employee import Employee
from .Singleton import SingletonMeta
from .Types import Document
from .Unit import ProductionStage, Unit
from .config import config
from .exceptions import EmployeeNotFoundError, UnitNotFoundError


def _get_database_credentials() -> str:
    """Get MongoDB connection url"""
    try:
        mongo_connection_url_env: tp.Optional[str] = os.getenv("MONGO_CONNECTION_URL")

        if mongo_connection_url_env is not None:
            return mongo_connection_url_env
        else:
            return config.mongo_db.mongo_connection_url

    except Exception as E:
        message: str = f"Failed to establish database connection: {E}. Exiting."
        logger.critical(message)
        sys.exit(1)


class MongoDbWrapper(metaclass=SingletonMeta):
    """handles interactions with MongoDB database"""

    @logger.catch
    def __init__(self) -> None:
        logger.info("Trying to connect to MongoDB")

        self._client: AsyncIOMotorClient = AsyncIOMotorClient(_get_database_credentials())
        self._database: AsyncIOMotorDatabase = self._client["Feecc-Hub"]

        # collections
        self._employee_collection: AsyncIOMotorCollection = self._database["Employee-data"]
        self._unit_collection: AsyncIOMotorCollection = self._database["Unit-data"]
        self._prod_stage_collection: AsyncIOMotorCollection = self._database["Production-stages-data"]

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
        return await collection_.find({"_id": 0}).to_list(length=None)  # type: ignore

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

    async def update_unit(self, unit: Unit) -> None:
        """update data about the unit in the DB"""
        for stage in unit.biography:
            if stage.is_in_db:
                await self.update_production_stage(stage)
            else:
                await self.upload_production_stage(stage)

        unit_dict = unit.dict_data()
        await self._update_document("uuid", unit.uuid, unit_dict, self._unit_collection)

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

        unit_dict = unit.dict_data()

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
        try:
            unit_dict: Document = await self._find_item("internal_id", unit_internal_id, self._unit_collection)  # type: ignore
            prod_stage_dicts = await self._find_many("parent_unit_uuid", unit_dict["uuid"], self._prod_stage_collection)
            prod_stages = [ProductionStage(**stage) for stage in prod_stage_dicts]
            unit_dict["biography"] = prod_stages
            unit = Unit(**unit_dict)
            unit.components_units = [await self.get_unit_by_internal_id(id_) for id_ in unit.components_internal_ids]
            return unit

        except Exception as E:
            logger.error(E)
            message: str = f"Could not find the Unit with int. id {unit_internal_id}. Does it exist?"
            raise UnitNotFoundError(message)
