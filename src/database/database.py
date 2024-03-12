from typing import Any

from loguru import logger
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.results import BulkWriteResult

from ._db_utils import _get_database_client
from src.config import CONFIG
from src.feecc_workbench.Types import Document


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

    def insert(self, collection: str, entity: dict[str, Any]) -> None:
        """Inserts the entity in the specified collection."""
        self._database[collection].insert_one(entity)

    def find(self, collection: str, filters: dict[str, Any] = {}, **kwargs) -> list[Document]:
        """Returns the list of all items if filter is not specified. Otherwise returns the whole collection."""
        return list(self._database[collection].find(filter=filters, **kwargs))
    
    def find_one(self, collection: str, filters: dict[str, Any]) -> Document | None:
        return self._database[collection].find_one(filter=filters)

    def update(self, collection: str, update: dict[str, Any], filters: dict[str, Any]) -> None:
        """Updates the specified document's fields."""
        self._database[collection].find_one_and_update(filter=filters, update=update)

    def delete(self, collection: str, filters: dict[str, Any]) -> None:
        """Deletes filtered results and returns it's number."""
        self._database[collection].delete_one(filter=filters)

    def bulk_write(self, collection: str, items: list[Any]) -> BulkWriteResult:
        """Inserts or updates multiple documents at once."""
        return self._database[collection].bulk_write(items)

    def aggregate(self, collection: str, pipeline: list[dict[str, Any]]) -> list[Document]:
        """Perform the aggregation and return matched Documents."""
        return list(self._database[collection].aggregate(pipeline))


BaseMongoDbWrapper = _BaseMongoDbWrapper()
