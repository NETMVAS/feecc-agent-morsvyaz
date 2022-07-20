import asyncio
from queue import Queue
from threading import Lock, Thread

from loguru import logger
from robonomicsinterface import Account, Datalog

from .config import CONFIG
from .database import MongoDbWrapper
from .Messenger import messenger
from .utils import async_time_execution, time_execution

ROBONOMICS_ACCOUNT: Account | None = None
DATALOG_CLIENT: Datalog | None = None
CLIENT_LOCK = Lock()

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
    queue: Queue[str] = Queue(maxsize=1)
    event = asyncio.Event()
    Thread(target=_post_to_datalog, args=(content, queue, event, CLIENT_LOCK)).start()

    await event.wait()
    if txn_hash := queue.get():
        logger.info(f"Adding {txn_hash=} to unit {unit_internal_id} data")
        await MongoDbWrapper().unit_update_single_field(unit_internal_id, "txn_hash", txn_hash)


@time_execution
def _post_to_datalog(content: str, queue: Queue[str], event: asyncio.Event, lock: Lock) -> None:
    """echo provided string to the Robonomics datalog"""
    assert DATALOG_CLIENT is not None, "Robonomics interface client has not been initialized"
    logger.info(f"Posting data '{content}' to Robonomics datalog")

    try:
        assert lock.acquire(timeout=180), "Failed to unlock Datalog client"
        txn_hash: str = DATALOG_CLIENT.record(data=content)
        message = f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}"
        messenger.success("Данные паспорта опубликованы в Даталоге сети Robonomics")
        logger.info(message)
    except Exception as e:
        logger.error(f"Failed to post to the Datalog: {e}")
        messenger.error("Не удалось записать данные паспорта в Даталог сети Robonomics")
        txn_hash = ""
    finally:
        if lock.locked():
            lock.release()

    queue.put(txn_hash)
    event.set()
