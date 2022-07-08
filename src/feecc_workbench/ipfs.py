import os
from typing import AnyStr

import httpx
from loguru import logger

from .config import CONFIG
from .Messenger import messenger
from .utils import async_time_execution, get_headers, service_is_up

IPFS_GATEWAY_ADDRESS: str = CONFIG.ipfs_gateway.ipfs_server_uri


@async_time_execution
async def publish_file(rfid_card_id: str, file_path: os.PathLike[AnyStr]) -> tuple[str, str]:
    """publish a provided file to IPFS using the Feecc gateway and return it's CID and URL"""
    if not CONFIG.ipfs_gateway.enable:
        raise ValueError("IPFS Gateway disabled in config")

    if not service_is_up(IPFS_GATEWAY_ADDRESS):
        message = "IPFS gateway is not available"
        messenger.error(message)
        raise ConnectionError(message)

    is_local_path: bool = os.path.exists(file_path)
    headers: dict[str, str] = get_headers(rfid_card_id)
    base_url = f"{IPFS_GATEWAY_ADDRESS}/publish-to-ipfs"

    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        if is_local_path:
            files = {"file_data": open(file_path, "rb")}
            response: httpx.Response = await client.post(url="/upload-file", headers=headers, files=files)
        else:
            json = {"absolute_path": str(file_path)}
            response = await client.post(url="/by-path", headers=headers, json=json)

    if response.is_error:
        messenger.error(f"IPFS gateway returned an error: {response.text}")
        raise httpx.RequestError(response.text)

    assert int(response.json().get("status", 500)) == 200, response.json()

    cid: str = response.json()["ipfs_cid"]
    link: str = response.json()["ipfs_link"]

    logger.info(f"File '{file_path} published to IPFS under CID {cid}'")

    return cid, link
