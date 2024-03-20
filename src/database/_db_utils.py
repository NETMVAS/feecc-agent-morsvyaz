import datetime as dt
import sys

from loguru import logger
from pymongo import MongoClient

from ..unit.Unit import Unit


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


def _get_unit_dict_data(unit: Unit) -> dict[str, str | bool | None | list[str] | dt.datetime]:
    return {
        "schema_id": unit.schema.schema_id,
        "uuid": unit.uuid,
        "internal_id": unit.internal_id,
        "certificate_ipfs_cid": unit.certificate_ipfs_cid,
        "txn_hash": unit.txn_hash,
        "serial_number": unit.serial_number,
        "components_internal_ids": unit.components_internal_ids,
        "featured_in_int_id": unit.featured_in_int_id,
        "creation_time": unit.creation_time,
        "status": unit.status.value,
    }
