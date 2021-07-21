from .exceptions import UnitNotFoundError
import typing as tp
from pymongo import MongoClient
from .Unit import Unit
from .Employee import Employee
from dataclasses import asdict


class MongoDbWrapper:
    """handles interactions with MongoDB database"""

    def __init__(self, username: str, password: str) -> None:
        mongo_client: str = f"mongodb+srv://{username}:{password}@netmvas.hx3jm.mongodb.net/Feecc-Hub?retryWrites=true&w=majority"
        self._client: MongoClient = MongoClient(mongo_client)
        self._database = self._client["Feecc-Hub"]
        self._employee_collection = self._database["Employee-data"]
        self._unit_collection = self._database["Unit-data"]
        self._prod_stage_collection = self._database["Production-stages-data "]

    @staticmethod
    def _upload_dict(document: tp.Dict[str, tp.Any], collection) -> None:
        """insert a document into specified collection"""
        collection.insert_one(document)

    def _upload_dataclass(self, dataclass, collection) -> None:
        """
        convert an arbitrary dataclass to dictionary and insert it
        into the desired collection in the database
        """
        dataclass_dict: tp.Dict[str, tp.Any] = asdict(dataclass)
        self._upload_dict(dataclass_dict, collection)

    @staticmethod
    def _find_item(key: str, value: str, collection) -> tp.Dict[str, tp.Any]:
        """
        finds one element in the specified collection, which has
        specified key matching specified value
        """
        return collection.find_one({key: value})

    @staticmethod
    def _find_many(key: str, value: str, collection) -> tp.List[tp.Dict[str, tp.Any]]:
        """
        finds all elements in the specified collection, which have
        specified key matching specified value
        """
        return collection.find({key: value})

    @staticmethod
    def _get_all_items_in_collection(collection) -> tp.List[tp.Dict[str, tp.Any]]:
        """get all documents in the provided collection"""
        return collection.find()

    def upload_employee(self, employee: Employee) -> None:
        self._upload_dataclass(employee, self._employee_collection)

    def upload_unit(self, unit: Unit) -> None:
        """
        convert a unit instance into a dictionary suitable for future reassembly removing
        unnecessary keys and converting nested structures and upload it
        """

        # get basic dict of unit
        base_dict = asdict(unit)

        # upload nested dataclasses
        map(self._upload_dataclass, unit.unit_biography)

        # removing unnecessary keys
        for key in ("_associated_passport", "_config", "unit_biography"):
            del base_dict[key]

        self._upload_dict(base_dict, self._unit_collection)

    def get_all_employees(self) -> tp.Tuple[Employee]:
        employee_data: tp.List[tp.Dict[str, str]] = self._get_all_items_in_collection(
            self._employee_collection
        )
        employees = tuple(Employee(**data) for data in employee_data)
        return employees

    def get_unit_by_internal_id(self, unit_internal_id: str) -> Unit:
        try:
            unit_dict = self._find_item("internal_id", unit_internal_id, self._unit_collection)
            unit = Unit(**unit_dict)
            return unit
        except Exception as e:
            raise UnitNotFoundError(e)
