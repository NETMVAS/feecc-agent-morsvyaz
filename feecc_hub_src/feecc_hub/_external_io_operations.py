import os
import threading
import typing as tp
from abc import ABC, abstractmethod

import ipfshttpclient
from loguru import logger
from pinatapy import PinataPy
from substrateinterface import Keypair, SubstrateInterface

from ._short_url_generator import update_short_url
from .exceptions import DatalogError, SubstrateError
from .Types import Config, ConfigSection


class File:
    """stores data about one file-like entity with related attributes"""

    def __init__(self, path: str, check_presence: bool = False) -> None:
        if check_presence and not os.path.exists(path):
            message = f"Path {path} doesn't point to an actual file"
            logger.error(message)
            raise FileNotFoundError(message)

        self.path: str = path
        self.filename: str = os.path.basename(self.path)
        self.ipfs_hash: tp.Optional[str] = None
        self.is_pinned: bool = False
        self.short_url: tp.Optional[str] = None
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

    def delete(self) -> None:
        """deletes the file"""
        try:
            os.remove(self.path)

            if self.qrcode is not None:
                os.remove(self.qrcode)

        except FileNotFoundError:
            pass


class ExternalIoGateway:
    def __init__(self, config: Config):
        self.config: Config = config

    def send(self, file: File) -> tp.Optional[str]:
        """Handle external IO operations, such as IPFS and Robonomics interactions"""
        if self.config["ipfs"]["enable"]:
            ipfs_worker = IpfsWorker(self, self.config)
            ipfs_worker.post(file)

            logger.debug(
                f"File parameters: {file.short_url, file.keyword, file.ipfs_hash}, file: {repr(file)}"
            )

            if file.keyword and file.ipfs_hash:
                logger.info(f"Updating URL {file.short_url}")
                update_short_url(file.keyword, file.ipfs_hash, self.config)

            if self.config["pinata"]["enable"]:
                pinata_worker = PinataWorker(self, self.config)
                pinata_worker.post(file)

        if self.config["robonomics_network"]["enable_datalog"] and file.ipfs_hash:
            try:
                robonomics_worker = RobonomicsWorker(self, self.config)
                robonomics_worker.post(file.ipfs_hash)
            except Exception as e:
                logger.error(f"Error writing IPFS hash to Robonomics datalog: {e}")

        return file.ipfs_hash


class BaseIoWorker(ABC):
    """
    abstract Io worker class for other worker to inherit from
    """

    def __init__(self, context: ExternalIoGateway, target: str) -> None:
        """
        :param context of type IoGateway which makes use of the class methods
        """
        logger.debug(f"An instance of {self.name} initialized at {self}")
        self.target: str = target
        self._context: ExternalIoGateway = context

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

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="IPFS")
        self.config: Config = config

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

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Robonomics Network")
        self.config: ConfigSection = config["robonomics_network"]

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
            datalog_total_number: int = (
                substrate.query("Datalog", "DatalogIndex", [account_address]).value["end"] - 1
            )
            datalog: str = substrate.query(
                "Datalog", "DatalogItem", [[account_address, datalog_total_number]]
            ).value["payload"]
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
            call = substrate.compose_call(
                call_module="Datalog", call_function="record", call_params={"record": data}
            )
            logger.info(f"Successfully created a call:\n{call}")
            logger.info("Creating extrinsic")
            extrinsic = substrate.create_signed_extrinsic(call=call, keypair=keypair)
        except Exception as e:
            logger.error(f"Failed to create an extrinsic: {e}")
            return None

        try:
            logger.info("Submitting extrinsic")
            receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            logger.info(
                f"Extrinsic {receipt.extrinsic_hash} sent and included in block {receipt.extrinsic_hash}"
            )
            return str(receipt.extrinsic_hash)
        except Exception as e:
            logger.error(f"Failed to submit extrinsic: {e}")
            return None

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

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Pinata cloud")
        self.config: ConfigSection = config["pinata"]

    def post(self, file: File) -> None:
        logger.info("Pinning file to Pinata in the background")
        pinata_thread = threading.Thread(target=self._pin_to_pinata, args=(file,))
        pinata_thread.start()
        logger.info(f"Pinning process started. Thread name: {pinata_thread.name}")

    def _pin_to_pinata(self, file: File) -> None:
        """pin files in Pinata Cloud to secure their copies in IPFS"""
        api_key = self.config["pinata_api"]
        api_token = self.config["pinata_secret_api"]
        pinata = PinataPy(api_key, api_token)
        logger.info(f"Starting publishing file {file.filename} to Pinata")
        pinata.pin_file_to_ipfs(file.path)
        logger.info(f"File {file.filename} published to Pinata")

    def get(self) -> None:
        raise NotImplementedError
