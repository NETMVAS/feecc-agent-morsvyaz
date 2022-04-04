import datetime as dt
import os
import sys
import typing as tp

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from feecc_workbench.Unit import Unit
from feecc_workbench.config import config


def _get_database_name() -> str:
    """Get DB name in cluster from a MongoDB connection url"""
    mongo_connection_url: str = os.getenv("MONGO_CONNECTION_URL", "") or config.mongo_db.mongo_connection_url
    db_name: str = mongo_connection_url.split("/")[-1]

    if "?" in db_name:
        db_name = db_name.split("?")[0]

    return db_name


def _get_database_client() -> AsyncIOMotorClient:
    """Get MongoDB connection url"""
    mongo_connection_url: str = os.getenv("MONGO_CONNECTION_URL", "") or config.mongo_db.mongo_connection_url

    try:
        db_client = AsyncIOMotorClient(mongo_connection_url, serverSelectionTimeoutMS=3000)
        db_client.server_info()
        return db_client

    except Exception as E:
        message = (
            f"Failed to establish database connection: {E}. "
            f"Is the provided URI correct? {mongo_connection_url=} Exiting."
        )
        logger.critical(message)
        sys.exit(1)


def _get_unit_dict_data(unit: Unit) -> tp.Dict[str, tp.Union[str, bool, None, tp.List[str], dt.datetime]]:
    return {
        "schema_id": unit.schema.schema_id,
        "uuid": unit.uuid,
        "internal_id": unit.internal_id,
        "is_in_db": unit.is_in_db,
        "passport_short_url": unit.passport_short_url,
        "passport_ipfs_cid": unit.passport_ipfs_cid,
        "components_internal_ids": unit.components_internal_ids,
        "featured_in_int_id": unit.featured_in_int_id,
        "creation_time": unit.creation_time,
        "status": unit.status.value,
    }
