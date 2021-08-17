import typing as tp
from abc import ABC, abstractmethod
from dataclasses import asdict

from pymongo import MongoClient

from .Employee import Employee
from .exceptions import UnitNotFoundError
from .Types import Collection, Config, Document
from .Unit import ProductionStage, Unit


class DbWrapper(ABC):
    """
    abstract database wrapper base class. implements common interfaces and
    declares common wrapper functionality
    """

    @abstractmethod
    def update_production_stage(self, updated_production_stage: ProductionStage) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_unit(self, unit: Unit) -> None:
        raise NotImplementedError

    @abstractmethod
    def upload_employee(self, employee: Employee) -> None:
        raise NotImplementedError

    @abstractmethod
    def upload_unit(self, unit: Unit) -> None:
        raise NotImplementedError

    @abstractmethod
    def upload_production_stage(self, production_stage: ProductionStage) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_all_employees(self) -> tp.List[Employee]:
        raise NotImplementedError

    @abstractmethod
    def get_unit_by_internal_id(self, unit_internal_id: str, config: Config) -> Unit:
        raise NotImplementedError


class MongoDbWrapper(DbWrapper):
    """handles interactions with MongoDB database"""

    def __init__(self, username: str, password: str, url: tp.Optional[str] = None) -> None:
        self._mongo_client_url: str = url or (
            f"mongodb+srv://{username}:{password}@netmvas.hx3jm.mongodb.net/Feecc-Hub?retryWrites=true&w=majority"
        )
        self._client: MongoClient = MongoClient(self._mongo_client_url)
        self._database = self._client["Feecc-Hub"]

        # collections
        self._employee_collection: Collection = self._database["Employee-data"]
        self._unit_collection: Collection = self._database["Unit-data"]
        self._prod_stage_collection: Collection = self._database["Production-stages-data"]

    @property
    def mongo_client_url(self) -> str:
        return self._mongo_client_url

    @property
    def mongo_client(self) -> MongoClient:
        return self._client

    @staticmethod
    def _upload_dict(document: Document, collection_: Collection) -> None:
        """insert a document into specified collection"""
        collection_.insert_one(document)

    def _upload_dataclass(self, dataclass: tp.Any, collection_: Collection) -> None:
        """
        convert an arbitrary dataclass to dictionary and insert it
        into the desired collection in the database
        """
        dataclass_dict: Document = asdict(dataclass)
        self._upload_dict(dataclass_dict, collection_)

    @staticmethod
    def _find_item(key: str, value: str, collection_: Collection) -> Document:
        """
        finds one element in the specified collection, which has
        specified key matching specified value
        """
        result: Document = collection_.find_one({key: value})
        del result["_id"]
        return result

    @staticmethod
    def _find_many(key: str, value: str, collection_: Collection) -> tp.List[Document]:
        """
        finds all elements in the specified collection, which have
        specified key matching specified value
        """
        result: tp.List[Document] = list(collection_.find({key: value}))

        for doc in result:
            del doc["_id"]

        return result

    @staticmethod
    def _get_all_items_in_collection(collection_: Collection) -> tp.List[Document]:
        """get all documents in the provided collection"""
        result: tp.List[Document] = list(collection_.find())

        for doc in result:
            del doc["_id"]

        return result

    @staticmethod
    def _update_document(key: str, value: str, new_document: Document, collection_: Collection) -> None:
        """
        finds matching document in the specified collection, and replaces it's data
        with what is provided in the new_document argument
        """
        collection_.find_one_and_update({key: value}, {"$set": new_document})

    def update_production_stage(self, updated_production_stage: ProductionStage) -> None:
        """update data about the production stage in the DB"""
        stage_dict: Document = asdict(updated_production_stage)
        stage_id: str = updated_production_stage.id
        self._update_document("id", stage_id, stage_dict, self._prod_stage_collection)

    def update_unit(self, unit: Unit) -> None:
        """update data about the unit in the DB"""
        if not unit.is_in_db:
            self.upload_unit(unit)
            return

        for stage in unit.unit_biography:
            if not stage.is_in_db:
                self.upload_production_stage(stage)
            else:
                self.update_production_stage(stage)

        base_dict = asdict(unit)
        for key in ("_associated_passport", "_config", "unit_biography"):
            del base_dict[key]

        self._update_document("uuid", unit.uuid, base_dict, self._unit_collection)

    def upload_employee(self, employee: Employee) -> None:
        self._upload_dataclass(employee, self._employee_collection)

    def upload_unit(self, unit: Unit) -> None:
        """
        convert a unit instance into a dictionary suitable for future reassembly removing
        unnecessary keys and converting nested structures and upload it
        """

        # get basic dict of unit
        unit.is_in_db = True
        base_dict = asdict(unit)

        # upload nested dataclasses
        for stage in unit.unit_biography:
            self.upload_production_stage(stage)

        # removing unnecessary keys
        for key in ("_associated_passport", "_config", "unit_biography"):
            del base_dict[key]

        self._upload_dict(base_dict, self._unit_collection)

    def upload_production_stage(self, production_stage: ProductionStage) -> None:
        if production_stage.is_in_db:
            return

        production_stage.is_in_db = True
        self._upload_dataclass(production_stage, self._prod_stage_collection)

    def get_all_employees(self) -> tp.List[Employee]:
        employee_data: tp.List[tp.Dict[str, str]] = self._get_all_items_in_collection(self._employee_collection)

        employees = [Employee(**data) for data in employee_data]
        return employees

    def get_unit_by_internal_id(self, unit_internal_id: str, config: Config) -> Unit:
        try:
            unit_dict: Document = self._find_item("internal_id", unit_internal_id, self._unit_collection)

            # get units biography
            prod_stage_dicts = self._find_many("parent_unit_uuid", unit_dict["uuid"], self._prod_stage_collection)
            prod_stages = [ProductionStage(**stage) for stage in prod_stage_dicts]
            unit_dict["unit_biography"] = prod_stages
            unit: Unit = Unit(config, **unit_dict)

            return unit

        except Exception as e:
            raise UnitNotFoundError(e)
