import os
import typing as tp

import httpx
from fastapi import Depends
from loguru import logger
from substrateinterface import Keypair, SubstrateInterface

from ._image_generation import create_qr
from ._short_url_generator import generate_short_url
from .config import config
from .exceptions import DatalogError, SubstrateError
from .utils import get_headers, time_execution

IO_GATEWAY_ADDRESS: str = config.workbench_config.feecc_io_gateway_socket


class File:
    """stores data about one file-like entity with related attributes"""

    def __init__(self, path: str, check_presence: bool = False, short_url: tp.Optional[str] = None) -> None:
        if check_presence and not os.path.exists(path):
            message: str = f"Path {path} doesn't point to an actual file"
            logger.error(message)
            raise FileNotFoundError(message)

        self.path: str = path
        self.filename: str = os.path.basename(self.path)
        self.ipfs_hash: tp.Optional[str] = None
        self.is_pinned: bool = False
        self.short_url: tp.Optional[str] = short_url
        self.qrcode: tp.Optional[str] = None

    @property
    def keyword(self) -> tp.Optional[str]:
        return self.short_url.split("/")[-1] if self.short_url else None

    @property
    def extension(self) -> str:
        sections = self.filename.split(".")
        return sections[-1] if sections else ""

    def __str__(self) -> str:
        """convert self into a string"""
        if self.extension not in ["yaml", "json", "txt", "log"]:
            return self.filename
        with open(self.path, "r") as f:
            return "\n".join(f.readlines())

    def generate_qr_code(self) -> str:
        """generate a QR code with the short link"""
        self.short_url = generate_short_url()
        self.qrcode = create_qr(self.short_url)
        return self.qrcode

    def delete(self) -> None:
        """deletes the file"""
        try:
            os.remove(self.path)

            if self.qrcode is not None:
                os.remove(self.qrcode)

        except FileNotFoundError:
            pass


class RobonomicsWorker:
    """Robonomics worker handles interactions with Robonomics network"""

    @logger.catch()
    def _get_substrate_connection(self) -> SubstrateInterface:
        """establish connection to a specified substrate node"""
        try:
            substrate_node_url: str = config.robonomics_network.substrate_node_url
            logger.info("Establishing connection to substrate node")
            substrate = SubstrateInterface(
                url=substrate_node_url,
                ss58_format=32,
                type_registry_preset="substrate-node-template",
                type_registry={
                    "types": {
                        "Record": "Vec<u8>",
                        "<T as frame_system::Config>::AccountId": "AccountId",
                        "RingBufferItem": {
                            "type": "struct",
                            "type_mapping": [
                                ["timestamp", "Compact<u64>"],
                                ["payload", "Vec<u8>"],
                            ],
                        },
                        "RingBufferIndex": {
                            "type": "struct",
                            "type_mapping": [
                                ["start", "Compact<u64>"],
                                ["end", "Compact<u64>"],
                            ],
                        },
                    }
                },
            )
            logger.info("Successfully established connection to substrate node")
            return substrate

        except Exception as E:
            message: str = f"Substrate connection failed: {E}"
            logger.error(message)
            raise SubstrateError(message)

    def _get_latest_datalog(self, account_address: str) -> str:
        """
        Fetch latest datalog record of a provided account
        Parameters
        ----------
        account_address: ss58 address of an account which datalog is to be fetched for
        Returns
        -------
        String, the latest record of specified account
        """
        try:
            substrate: SubstrateInterface = self._get_substrate_connection()
            datalog_total_number: int = substrate.query("Datalog", "DatalogIndex", [account_address]).value["end"] - 1
            datalog: str = substrate.query("Datalog", "DatalogItem", [[account_address, datalog_total_number]]).value[
                "payload"
            ]
            return datalog

        except Exception as E:
            message: str = f"Error fetching latest datalog: {E}"
            logger.error(message)
            raise DatalogError(message)

    def _write_datalog(self, data: str) -> tp.Optional[str]:
        """
        Write any string to datalog
        Parameters
        ----------
        data : data to be written as datalog
        Returns
        -------
        Hash of the datalog transaction
        """
        substrate: SubstrateInterface = self._get_substrate_connection()
        seed: str = config.robonomics_network.account_seed
        # create keypair
        try:
            keypair = Keypair.create_from_mnemonic(seed, ss58_format=32)
        except Exception as E:
            logger.error(f"Failed to create keypair: \n{E}")
            return None

        try:
            logger.info("Creating substrate call")
            call = substrate.compose_call(call_module="Datalog", call_function="record", call_params={"record": data})
            logger.info(f"Successfully created a call:\n{call}")
            logger.info("Creating extrinsic")
            extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
        except Exception as E:
            logger.error(f"Failed to create an extrinsic: {E}")
            return None

        try:
            logger.info("Submitting extrinsic")
            receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            logger.info(f"Extrinsic {receipt.extrinsic_hash} sent and included in block {receipt.extrinsic_hash}")
            return str(receipt.extrinsic_hash)
        except Exception as E:
            logger.error(f"Failed to submit extrinsic: {E}")
            return None

    @time_execution
    def post(self, data: tp.Union[File, str]) -> None:
        """write provided string to Robonomics datalog"""
        data_: str = str(data)
        transaction_hash: tp.Optional[str] = self._write_datalog(data_)
        logger.info(f"Data added to Robonomics datalog. Transaction hash: {transaction_hash}")

    def get(self) -> str:
        """get latest datalog post for the account"""
        account_address: str = config.robonomics_network.account_address
        return self._get_latest_datalog(account_address)


async def publish_to_ipfs(file_path: str, headers: tp.Dict[str, str] = Depends(get_headers)) -> tp.Tuple[str, str]:
    """publish a provided file to IPFS using the Feecc gateway and return it's CID and URL"""

    async with httpx.AsyncClient() as client:
        url = f"{IO_GATEWAY_ADDRESS}/io-gateway/ipfs"
        payload = {"filename": file_path, "background_processing": False}
        response: httpx.Response = await client.post(url=url, headers=headers, json=payload)

    if response.is_error:
        raise httpx.RequestError(response.text)

    cid: str = response.json()["ipfs_cid"]
    link: str = response.json()["ipfs_link"]

    logger.info(f"File '{file_path} published to IPFS under CID {cid}'")

    return cid, link


async def publish_to_pinata(file_path: str, headers: tp.Dict[str, str] = Depends(get_headers)) -> tp.Tuple[str, str]:
    """publish a provided file to Pinata using the Feecc gateway and return it's CID and URL"""

    async with httpx.AsyncClient() as client:
        url = f"{IO_GATEWAY_ADDRESS}/io-gateway/pinata"
        payload = {"filename": file_path, "background_processing": True}
        response: httpx.Response = await client.post(url=url, headers=headers, json=payload)

    if response.is_error:
        raise httpx.RequestError(response.text)

    cid: str = response.json()["ipfs_cid"]
    link: str = response.json()["ipfs_link"]

    logger.info(f"File '{file_path} published to Pinata under CID {cid}'")

    return cid, link


async def publish_file(file_path: str) -> tp.Optional[tp.Tuple[str, str]]:
    """publish a file to pinata or IPFS according to config"""
    if config.pinata.enable:
        return await publish_to_pinata(file_path)
    elif config.ipfs.enable:
        return await publish_to_ipfs(file_path)
    else:
        logger.warning(f"File '{file_path}' is neither published to Pinata, nor IPFS as both options are disabled")
        return None


async def print_image(
    file_path: str, annotation: tp.Optional[str] = None, headers: tp.Dict[str, str] = Depends(get_headers)
) -> None:
    """print the provided image file"""

    async with httpx.AsyncClient() as client:
        url = f"{IO_GATEWAY_ADDRESS}/printing/print_image"
        payload = {"annotation": annotation}
        files = {"upload-file": (None, open(file_path, "rb"), "image/png")}
        response: httpx.Response = await client.post(url=url, headers=headers, json=payload, files=files)

    if response.is_error:
        raise httpx.RequestError(response.text)

    logger.info(f"Printed image '{file_path}'")
