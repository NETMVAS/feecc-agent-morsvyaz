import asyncio

from loguru import logger
from robonomicsinterface import Account, Datalog

from .config import CONFIG
from .database import MongoDbWrapper
from .exceptions import RobonomicsError
from .Messenger import messenger
from .utils import async_time_execution
from .translation import translation


class AsyncDatalogClient(Datalog):  # type: ignore
    """Async thread safe Datalog client implementation"""

    _client_lock: asyncio.Lock = asyncio.Lock()

    async def record(self, data: str, nonce: int | None = None) -> str:
        async with self._client_lock:
            try:
                loop = asyncio.get_running_loop()
                result: str = await loop.run_in_executor(None, super().record, data)
                return result
            except Exception as e:
                raise RobonomicsError(str(e)) from e


ROBONOMICS_ACCOUNT: Account | None = None

if CONFIG.robonomics.enable_datalog:
    ROBONOMICS_ACCOUNT = Account(
        seed=CONFIG.robonomics.account_seed,
        remote_ws=CONFIG.robonomics.substrate_node_uri,
    )


@async_time_execution
async def post_to_datalog(content: str, unit_internal_id: str) -> None:
    assert ROBONOMICS_ACCOUNT is not None, "Robonomics credentials have not been provided"
    datalog_client = AsyncDatalogClient(
        account=ROBONOMICS_ACCOUNT,
        wait_for_inclusion=False,
    )
    logger.info(f"Posting data '{content}' to Robonomics datalog")
    retry_cnt = 3
    txn_hash: str = ""

    for i in range(1, retry_cnt + 1):
        try:
            txn_hash = await datalog_client.record(data=content)
            break
        except Exception as e:
            logger.error(f"Failed to post to the Datalog (attempt {i}/{retry_cnt}): {e}")
            if i < retry_cnt:
                continue
            messenger.error(translation('FailedToWrite'))
            raise e

    assert txn_hash
    await MongoDbWrapper().unit_update_single_field(unit_internal_id, "txn_hash", txn_hash)
    message = f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}"
    messenger.success(translation('DataPublished'))
    logger.info(message)

