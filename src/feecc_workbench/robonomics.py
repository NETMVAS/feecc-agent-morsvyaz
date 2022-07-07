from loguru import logger
from robonomicsinterface import Account, Datalog

from .config import CONFIG
from .database import MongoDbWrapper
from .utils import async_time_execution, emit_error

ROBONOMICS_ACCOUNT: Account | None = None
DATALOG_CLIENT: Datalog | None = None

if CONFIG.robonomics.enable_datalog:
    ROBONOMICS_ACCOUNT = Account(
        seed=CONFIG.robonomics.account_seed,
        remote_ws=CONFIG.robonomics.substrate_node_uri,
    )
    DATALOG_CLIENT = Datalog(
        account=ROBONOMICS_ACCOUNT,
        wait_for_inclusion=False,
    )


@async_time_execution
async def post_to_datalog(content: str, unit_internal_id: str) -> None:
    """
    for now Robonomics interface library doesn't support async io.
    This operation requires waiting for the block to be written in the blockchain,
    which takes 15 seconds on average, so it's done in another thread
    """
    assert DATALOG_CLIENT is not None, "Robonomics interface client has not been initialized"
    logger.info(f"Posting data '{content}' to Robonomics datalog")

    try:
        txn_hash: str = DATALOG_CLIENT.record(data=content)
    except Exception as e:
        message = f"An error ocurred while posting to Robonomics Datalog: {e}"
        logger.error(message)
        emit_error(message)

    logger.info(f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}")
    logger.info(f"Adding {txn_hash=} to unit {unit_internal_id} data")
    await MongoDbWrapper().unit_update_single_field(unit_internal_id, "txn_hash", txn_hash)
