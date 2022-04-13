import datetime as dt
import sys
import typing as tp

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from feecc_workbench.Unit import Unit


def _get_database_client(mongo_connection_uri: str) -> AsyncIOMotorClient:
    """Get MongoDB connection url"""
    try:
        db_client = AsyncIOMotorClient(mongo_connection_uri, serverSelectionTimeoutMS=3000)
        db_client.server_info()
        return db_client

    except Exception as E:
        message = (
            f"Failed to establish database connection: {E}. "
            f"Is the provided URI correct? {mongo_connection_uri=} Exiting."
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
