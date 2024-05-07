import sys

from loguru import logger
from pymongo import MongoClient


def _get_database_client(mongo_connection_uri: str) -> MongoClient:
    """Get MongoDB connection url"""
    try:
        db_client: MongoClient = MongoClient(mongo_connection_uri)
        return db_client

    except Exception as e:
        message = (
            f"Failed to establish database connection: {e}. "
            f"Is the provided URI correct? {mongo_connection_uri=} Exiting."
        )
        logger.critical(message)
        sys.exit(1)

