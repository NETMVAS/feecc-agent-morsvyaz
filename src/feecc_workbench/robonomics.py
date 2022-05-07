from loguru import logger
from robonomicsinterface import RobonomicsInterface

from .config import CONFIG
from .database import MongoDbWrapper
from .utils import async_time_execution

if CONFIG.robonomics.enable_datalog:
    ROBONOMICS_CLIENT = RobonomicsInterface(
        seed=CONFIG.robonomics.account_seed or None,
        remote_ws=CONFIG.robonomics.substrate_node_uri or None,
    )
else:
    ROBONOMICS_CLIENT = None


@async_time_execution
async def post_to_datalog(content: str, unit_internal_id: str) -> None:
    """echo provided string to the Robonomics datalog"""
    assert ROBONOMICS_CLIENT is not None, "Robonomics interface client has not been initialized"
    logger.info(f"Posting data '{content}' to Robonomics datalog")
    txn_hash: str = ROBONOMICS_CLIENT.record_datalog(content)
    logger.info(f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}")

    logger.info(f"Adding {txn_hash=} to unit {unit_internal_id} data")
    unit = await MongoDbWrapper().get_unit_by_internal_id(unit_internal_id)
    unit.txn_hash = txn_hash
    await MongoDbWrapper().update_unit(unit, include_keys=["txn_hash"])
    logger.info(f"{unit_internal_id} data has been updated")
