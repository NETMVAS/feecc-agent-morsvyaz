import asyncio

from loguru import logger
from robonomicsinterface import Account, Datalog

from .config import CONFIG
from .database import MongoDbWrapper
from .Messenger import messenger
from .utils import async_time_execution


class AsyncDatalogClient(Datalog):  # type: ignore
    """Async thread safe Datalog client implementation"""

    _client_lock: asyncio.Lock = asyncio.Lock()

    async def record(self, data: str, nonce: int | None = None) -> str:
        async with self._client_lock:
            loop = asyncio.get_running_loop()
            result: str = await loop.run_in_executor(None, super().record, data)
            return result


ROBONOMICS_ACCOUNT: Account | None = None
DATALOG_CLIENT: AsyncDatalogClient | None = None

if CONFIG.robonomics.enable_datalog:
    ROBONOMICS_ACCOUNT = Account(
        seed=CONFIG.robonomics.account_seed,
        remote_ws=CONFIG.robonomics.substrate_node_uri,
    )
    DATALOG_CLIENT = AsyncDatalogClient(
        account=ROBONOMICS_ACCOUNT,
        wait_for_inclusion=False,
    )


@async_time_execution
async def post_to_datalog(content: str, unit_internal_id: str) -> None:
    assert DATALOG_CLIENT is not None, "Robonomics interface client has not been initialized"
    logger.info(f"Posting data '{content}' to Robonomics datalog")
    retry_cnt = 3
    txn_hash: str = ""

    for i in range(1, retry_cnt + 1):
        try:
            txn_hash = await DATALOG_CLIENT.record(data=content)
            break
        except Exception as e:
            logger.error(f"Failed to post to the Datalog (attempt {i}/{retry_cnt}): {e}")
            if i < retry_cnt:
                continue
            messenger.error("Не удалось записать данные паспорта в Даталог сети Robonomics")
            raise e

    assert txn_hash
    message = f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}"
    messenger.success("Данные паспорта опубликованы в Даталоге сети Robonomics")
    logger.info(message)

    await MongoDbWrapper().unit_update_single_field(unit_internal_id, "txn_hash", txn_hash)
