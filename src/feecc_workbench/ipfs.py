import pathlib

import httpx
from loguru import logger

from .config import CONFIG
from .Messenger import messenger
from .utils import async_time_execution, get_headers, service_is_up

IPFS_GATEWAY_ADDRESS: str = CONFIG.ipfs_gateway.ipfs_server_uri


@async_time_execution
async def publish_file(rfid_card_id: str, file_path: pathlib.Path) -> tuple[str, str]:
    """publish a provided file to IPFS using the Feecc gateway and return it's CID and URL"""
    if not CONFIG.ipfs_gateway.enable:
        raise ValueError("IPFS Gateway disabled in config")

    if not service_is_up(IPFS_GATEWAY_ADDRESS):
        message = "IPFS gateway is not available"
        messenger.error("IPFS шлюз недоступен")
        raise ConnectionError(message)

    file_path = pathlib.Path(file_path)
    headers: dict[str, str] = get_headers(rfid_card_id)
    base_url = f"{IPFS_GATEWAY_ADDRESS}/publish-to-ipfs"

    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        if file_path.exists():
            with file_path.open("rb") as f:
                files = {"file_data": f}
                response: httpx.Response = await client.post(url="/upload-file", headers=headers, files=files)
        else:
            json = {"absolute_path": str(file_path)}
            response = await client.post(url="/by-path", headers=headers, json=json)

    if response.is_error:
        messenger.error(f"Ошибка шлюза IPFS: {response.json().get('detail', '')}")
        raise httpx.RequestError(response.json().get("detail", ""))

    assert int(response.json().get("status", 500)) == 200, response.json()

    cid: str = response.json().get("ipfs_cid")
    link: str = response.json().get("ipfs_link")
    assert cid and link, "IPFS gateway returned no CID"

    logger.info(f"File '{file_path} published to IPFS under CID {cid}'")

    return cid, link
