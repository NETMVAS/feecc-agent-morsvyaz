import typing as tp
from dataclasses import asdict

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from .Employee import Employee
from .Singleton import SingletonMeta
from .Types import Document, GlobalConfig
from .Unit import ProductionStage, Unit
from .exceptions import EmployeeNotFoundError, UnitNotFoundError


class MongoDbWrapper(metaclass=SingletonMeta):
    """handles interactions with MongoDB database"""

    def __init__(self, mongo_client_url: str) -> None:
        logger.info("Trying to connect to MongoDB")

        self._client: AsyncIOMotorClient = AsyncIOMotorClient(mongo_client_url)
        self._database: AsyncIOMotorDatabase = self._client["Feecc-Hub"]

        # collections
        self._employee_collection: AsyncIOMotorCollection = self._database["Employee-data"]
        self._unit_collection: AsyncIOMotorCollection = self._database["Unit-data"]
        self._prod_stage_collection: AsyncIOMotorCollection = self._database["Production-stages-data"]

        logger.info("Successfully connected to MongoDB")

    @property
    def mongo_client(self) -> AsyncIOMotorClient:
        return self._client

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
        if not unit.is_in_db:
            await self.upload_unit(unit)
            return

        for stage in unit.unit_biography:
            if stage.is_in_db:
                await self.update_production_stage(stage)
            else:
                await self.upload_production_stage(stage)

        base_dict = asdict(unit)
        for key in ("_associated_passport", "_config", "unit_biography", "employee"):
            del base_dict[key]

        await self._update_document("uuid", unit.uuid, base_dict, self._unit_collection)

    async def upload_employee(self, employee: Employee) -> None:
        await self._upload_dataclass(employee, self._employee_collection)

    async def upload_unit(self, unit: Unit) -> None:
        """
        convert a unit instance into a dictionary suitable for future reassembly removing
        unnecessary keys and converting nested structures and upload it
        """

        # get basic dict of unit
        unit.is_in_db = True
        base_dict = asdict(unit)

        # upload nested dataclasses
        for stage in unit.unit_biography:
            await self.upload_production_stage(stage)

        # removing unnecessary keys
        for key in ("_associated_passport", "_config", "unit_biography", "employee"):
            del base_dict[key]

        await self._upload_dict(base_dict, self._unit_collection)

    async def upload_production_stage(self, production_stage: ProductionStage) -> None:
        if production_stage.is_in_db:
            return

        production_stage.is_in_db = True
        await self._upload_dataclass(production_stage, self._prod_stage_collection)

    async def get_all_employees(self) -> tp.List[Employee]:
        employee_data: tp.List[tp.Dict[str, str]] = await self._get_all_items_in_collection(self._employee_collection)
        return [Employee(**data) for data in employee_data]

    async def get_employee_by_card_id(self, card_id: str) -> Employee:
        """find the employee with the provided RFID card id"""
        employee_data: tp.Optional[Document] = await self._find_item("rfid_card_id", card_id, self._employee_collection)

        if employee_data is None:
            message = f"No employee with card ID {card_id}"
            logger.error(message)
            raise EmployeeNotFoundError(message)

        return Employee(**employee_data)

    async def get_unit_by_internal_id(self, unit_internal_id: str, config: GlobalConfig) -> Unit:
        try:
            unit_dict: Document = await self._find_item("internal_id", unit_internal_id, self._unit_collection)
            prod_stage_dicts = await self._find_many("parent_unit_uuid", unit_dict["uuid"], self._prod_stage_collection)
            prod_stages = [ProductionStage(**stage) for stage in prod_stage_dicts]
            unit_dict["unit_biography"] = prod_stages
            return Unit(config, **unit_dict)

        except Exception as E:
            raise UnitNotFoundError(E)
