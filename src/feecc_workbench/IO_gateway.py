from __future__ import annotations

import os
import typing as tp

import httpx
from loguru import logger
from robonomicsinterface import RobonomicsInterface

from ._image_generation import create_qr
from .config import Config
from .database import MongoDbWrapper
from .utils import get_headers, time_execution

PRINT_SERVER_ADDRESS: str = Config.printer.print_server_uri
IPFS_GATEWAY_ADDRESS: str = Config.ipfs_gateway.ipfs_server_uri
ROBONOMICS_CLIENT = RobonomicsInterface(
    seed=Config.robonomics.account_seed or None,
    remote_ws=Config.robonomics.substrate_node_uri or None,
)


@time_execution
def generate_qr_code(target_link: str) -> str:
    """generate a QR code"""
    return create_qr(target_link)


@time_execution
async def post_to_datalog(content: str, unit_internal_id: str) -> None:
    """echo provided string to the Robonomics datalog"""
    logger.info(f"Posting data '{content}' to Robonomics datalog")
    txn_hash: str = ROBONOMICS_CLIENT.record_datalog(content)
    logger.info(f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}")

    logger.info(f"Adding {txn_hash=} to unit {unit_internal_id} data")
    unit = await MongoDbWrapper().get_unit_by_internal_id(unit_internal_id)
    unit.txn_hash = txn_hash
    await MongoDbWrapper().update_unit(unit, include_keys=["txn_hash"])
    logger.info(f"{unit_internal_id} data has been updated")


@time_execution
async def publish_file(rfid_card_id: str, file_path: os.PathLike[tp.AnyStr]) -> tp.Tuple[str, str]:
    """publish a provided file to IPFS using the Feecc gateway and return it's CID and URL"""
    if not Config.ipfs_gateway.enable:
        raise ValueError("IPFS Gateway disabled in config")

    is_local_path: bool = os.path.exists(file_path)
    headers: tp.Dict[str, str] = get_headers(rfid_card_id)
    base_url = f"{IPFS_GATEWAY_ADDRESS}/publish-to-ipfs"

    async with httpx.AsyncClient(base_url=base_url, timeout=None) as client:
        if is_local_path:
            files = {"file_data": open(file_path, "rb")}
            response: httpx.Response = await client.post(url="/upload-file", headers=headers, files=files)
        else:
            json = {"absolute_path": str(file_path)}
            response = await client.post(url="/by-path", headers=headers, json=json)

    if response.is_error:
        raise httpx.RequestError(response.text)

    assert int(response.json().get("status", 500)) == 200, response.json()

    cid: str = response.json()["ipfs_cid"]
    link: str = response.json()["ipfs_link"]

    logger.info(f"File '{file_path} published to IPFS under CID {cid}'")

    return cid, link


@time_execution
async def print_image(file_path: str, rfid_card_id: str, annotation: tp.Optional[str] = None) -> None:
    """print the provided image file"""
    if not Config.printer.enable:
        logger.warning("Printer disabled, task dropped")
        return

    async with httpx.AsyncClient() as client:
        url = f"{PRINT_SERVER_ADDRESS}/print_image"
        headers: tp.Dict[str, str] = get_headers(rfid_card_id)
        data = {"annotation": annotation}
        files = {"image_file": open(file_path, "rb")}
        response: httpx.Response = await client.post(url=url, headers=headers, data=data, files=files)

    if response.is_error:
        raise httpx.RequestError(response.text)

    logger.info(f"Printed image '{file_path}'")
