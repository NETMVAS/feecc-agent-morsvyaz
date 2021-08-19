import os
import threading
import typing as tp
from abc import ABC, abstractmethod

import ipfshttpclient
import requests
from loguru import logger
from pinatapy import PinataPy
from substrateinterface import Keypair, SubstrateInterface

from .Singleton import SingletonMeta
from .Types import GlobalConfig, ConfigSection
from .Config import Config
from ._image_generation import create_qr
from ._short_url_generator import generate_short_url, update_short_url
from .exceptions import DatalogError, SubstrateError
from .utils import time_execution


class File:
    """stores data about one file-like entity with related attributes"""

    def __init__(self, path: str, check_presence: bool = False, short_url: tp.Optional[str] = None) -> None:
        if check_presence and not os.path.exists(path):
            message = f"Path {path} doesn't point to an actual file"
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
        if self.extension in ["yaml", "json", "txt", "log"]:
            with open(self.path, "r") as f:
                return "\n".join(f.readlines())
        else:
            return self.filename

    def generate_qr_code(self, config: GlobalConfig) -> str:
        """generate a QR code with the short link"""
        logger.debug("Generating short url (a dummy for now)")
        short_url: str = generate_short_url(config)
        self.short_url = short_url
        logger.debug("Generating QR code image file")
        qr_code_image: str = create_qr(short_url, config)
        self.qrcode = qr_code_image
        return qr_code_image

    def delete(self) -> None:
        """deletes the file"""
        try:
            os.remove(self.path)

            if self.qrcode is not None:
                os.remove(self.qrcode)

        except FileNotFoundError:
            pass


class ExternalIoGateway(metaclass=SingletonMeta):
    @property
    def config(self) -> GlobalConfig:
        return Config().global_config

    @time_execution
    def send(self, file: File) -> tp.Optional[str]:
        """Handle external IO operations, such as IPFS and Robonomics interactions"""
        if self.config["ipfs"]["enable"]:
            ipfs_worker = IpfsWorker()
            ipfs_worker.post(file)

            logger.debug(f"File parameters: {file.short_url, file.keyword, file.ipfs_hash}, file: {repr(file)}")

            if file.keyword and file.ipfs_hash:
                logger.info(f"Updating URL {file.short_url}")
                update_short_url(file.keyword, file.ipfs_hash, self.config)

            if self.config["pinata"]["enable"]:
                pinata_worker = PinataWorker()
                pinata_worker.post(file)

        if self.config["robonomics_network"]["enable_datalog"] and file.ipfs_hash:
            try:
                robonomics_worker = RobonomicsWorker()
                robonomics_worker.post(file.ipfs_hash)
            except Exception as e:
                logger.error(f"Error writing IPFS hash to Robonomics datalog: {e}")

        return file.ipfs_hash


class BaseIoWorker(ABC):
    """abstract Io worker class for other worker to inherit from"""

    @property
    def config(self) -> GlobalConfig:
        return Config().global_config

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    @tp.no_type_check
    def post(self, *args, **kwargs) -> None:
        """uploading data to the target"""
        raise NotImplementedError

    @abstractmethod
    @tp.no_type_check
    def get(self, *args, **kwargs) -> None:
        """getting data from the target"""
        raise NotImplementedError


class IpfsWorker(BaseIoWorker):
    """IPFS worker handles interactions with IPFS"""

    @time_execution
    def post(self, file: File) -> None:
        """publish file on IPFS"""
        ipfs_client = ipfshttpclient.connect()
        result = ipfs_client.add(file.path)
        ipfs_hash: str = result["Hash"]
        logger.info(f"File {file.filename} published to IPFS, hash: {ipfs_hash}")
        file.ipfs_hash = ipfs_hash

    def get(self) -> None:
        raise NotImplementedError


class RobonomicsWorker(BaseIoWorker):
    """Robonomics worker handles interactions with Robonomics network"""

    @property
    def config(self) -> ConfigSection:
        return Config().global_config["robonomics_network"]

    def _get_substrate_connection(self) -> SubstrateInterface:
        """establish connection to a specified substrate node"""
        try:
            substrate_node_url: str = self.config["substrate_node_url"]
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

        except Exception as e:
            message: str = f"Substrate connection failed: {e}"
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

        except Exception as e:
            message: str = f"Error fetching latest datalog: {e}"
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
        seed: str = self.config["account_seed"]
        # create keypair
        try:
            keypair = Keypair.create_from_mnemonic(seed, ss58_format=32)
        except Exception as e:
            logger.error(f"Failed to create keypair: \n{e}")
            return None

        try:
            logger.info("Creating substrate call")
            call = substrate.compose_call(call_module="Datalog", call_function="record", call_params={"record": data})
            logger.info(f"Successfully created a call:\n{call}")
            logger.info("Creating extrinsic")
            extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
        except Exception as e:
            logger.error(f"Failed to create an extrinsic: {e}")
            return None

        try:
            logger.info("Submitting extrinsic")
            receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            logger.info(f"Extrinsic {receipt.extrinsic_hash} sent and included in block {receipt.extrinsic_hash}")
            return str(receipt.extrinsic_hash)
        except Exception as e:
            logger.error(f"Failed to submit extrinsic: {e}")
            return None

    @time_execution
    def post(self, data: tp.Union[File, str]) -> None:
        """write provided string to Robonomics datalog"""
        data_: str = str(data)
        transaction_hash: tp.Optional[str] = self._write_datalog(data_)
        logger.info(f"Data added to Robonomics datalog. Transaction hash: {transaction_hash}")

    def get(self) -> str:
        """get latest datalog post for the account"""
        account_address: str = self.config["account_address"]
        return self._get_latest_datalog(account_address)


class PinataWorker(BaseIoWorker):
    """Pinata worker handles interactions with Pinata"""

    @property
    def config(self) -> ConfigSection:
        return Config().global_config["pinata"]

    @time_execution
    def post(self, file: File, direct_pin: bool = True) -> None:
        """pin files in Pinata Cloud to secure their copies in IPFS"""
        if direct_pin:
            logger.info("Pinning file to Pinata in the background")
            pinata_thread = threading.Thread(target=self._pin_to_pinata_over_tcp, args=(file,))
            pinata_thread.start()
            logger.info(f"Pinning process started. Thread name: {pinata_thread.name}")
        else:
            if file.ipfs_hash is None:
                logger.error("Can't pin to Pinata: IPFS hash is None")
                return
            logger.info(f"Starting publishing file {file.filename} to Pinata")
            self._pin_by_ipfs_hash(file.ipfs_hash, file.filename)
            logger.info(f"File {file.filename} published to Pinata")

    def _pin_by_ipfs_hash(self, ipfs_hash: str, filename: str) -> None:
        """push file to pinata using its hash"""
        headers: tp.Dict[str, str] = {
            "pinata_api_key": self.config["pinata_api"],
            "pinata_secret_api_key": self.config["pinata_secret_api"],
        }
        payload: tp.Dict[str, tp.Any] = {"pinataMetadata": {"name": filename}, "hashToPin": ipfs_hash}
        url: str = "https://api.pinata.cloud/pinning/pinByHash"
        response: tp.Any = requests.post(url=url, json=payload, headers=headers)
        logger.debug(f"Pinata API response: {response.json()}")

    def _pin_to_pinata_over_tcp(self, file: File) -> None:
        """pin files in Pinata Cloud to secure their copies in IPFS"""
        api_key = self.config["pinata_api"]
        api_token = self.config["pinata_secret_api"]
        pinata = PinataPy(api_key, api_token)
        logger.info(f"Starting publishing file {file.filename} to Pinata")
        pinata.pin_file_to_ipfs(file.path)
        logger.info(f"File {file.filename} published to Pinata")

    def get(self) -> None:
        raise NotImplementedError
