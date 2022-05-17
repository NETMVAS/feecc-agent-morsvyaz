import asyncio
from queue import Queue
from threading import Lock, Thread

from loguru import logger
from robonomicsinterface import RobonomicsInterface

from .config import CONFIG
from .database import MongoDbWrapper
from .utils import async_time_execution, time_execution

if CONFIG.robonomics.enable_datalog:
    ROBONOMICS_CLIENT = RobonomicsInterface(
        seed=CONFIG.robonomics.account_seed or None,
        remote_ws=CONFIG.robonomics.substrate_node_uri or None,
    )
else:
    ROBONOMICS_CLIENT = None

CLIENT_LOCK = Lock()


@async_time_execution
async def post_to_datalog(content: str, unit_internal_id: str) -> None:
    """
    for now Robonomics interface library doesn't support async io.
    This operation requires waiting for the block to be written in the blockchain,
    which takes 15 seconds on average, so it's done in another thread
    """
    assert ROBONOMICS_CLIENT is not None, "Robonomics interface client has not been initialized"

    queue: Queue[str] = Queue(maxsize=1)
    event = asyncio.Event()
    Thread(target=_post_to_datalog, args=(content, queue, event, CLIENT_LOCK)).start()

    await event.wait()
    txn_hash = queue.get()

    logger.info(f"Adding {txn_hash=} to unit {unit_internal_id} data")
    await MongoDbWrapper().unit_update_single_field(unit_internal_id, "txn_hash", txn_hash)


@time_execution
def _post_to_datalog(content: str, queue: Queue[str], event: asyncio.Event, lock: Lock) -> None:
    """echo provided string to the Robonomics datalog"""
    logger.info(f"Posting data '{content}' to Robonomics datalog")

    lock.acquire(timeout=180)
    txn_hash: str = ROBONOMICS_CLIENT.record_datalog(content)
    lock.release()

    logger.info(f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}")
    queue.put(txn_hash)
    event.set()
