import logging
import subprocess
import threading
import typing as tp
from abc import ABC, abstractmethod

import ipfshttpclient
from pinatapy import PinataPy

from ._Types import Config
from ._short_url_generator import update_short_url


class ExternalIoGateway:
    def __init__(self, config: Config):
        self.config: Config = config

    def send(self, filename: str, keyword: str = "") -> tp.Optional[str]:
        """Handle external IO operations, such as IPFS and Robonomics interactions"""
        ipfs_hash: str = ""

        if self.config["ipfs"]["enable"]:
            ipfs_worker = IpfsWorker(self, self.config)
            ipfs_hash = ipfs_worker.post(filename)

            if keyword and ipfs_hash:
                logging.info(f"Updating URL with keyword {keyword}")
                update_short_url(keyword, ipfs_hash, self.config)

            if self.config["pinata"]["enable"]:
                pinata_worker = PinataWorker(self, self.config)
                pinata_worker.post(filename)

        if self.config["datalog"]["enable"] and ipfs_hash:
            try:
                robonomics_worker = RobonomicsWorker(self, self.config)
                robonomics_worker.post(ipfs_hash)
            except Exception as e:
                logging.error(f"Error writing IPFS hash to Robonomics datalog: {e}")

            return ipfs_hash

        return None


class BaseIoWorker(ABC):
    """
    abstract Io worker class for other worker to inherit from
    """

    def __init__(self, context: ExternalIoGateway, target: str) -> None:
        """
        :param context of type IoGateway which makes use of the class methods
        """
        logging.debug(f"An instance of {self.name} initialized at {self}")
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

    def post(self, filename: str) -> str:
        """share file on IPFS"""
        ipfs_client = ipfshttpclient.connect()
        result = ipfs_client.add(filename)
        ipfs_hash: str = result["Hash"]
        logging.info(f"File {filename} published to IPFS, hash: {ipfs_hash}")
        return ipfs_hash

    def get(self) -> None:
        raise NotImplementedError


class RobonomicsWorker(BaseIoWorker):
    """Robonomics worker handles interactions with Robonomics network"""

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Robonomics Network")
        self.config: tp.Dict[str, tp.Any] = config["transaction"]

    def post(self, data: str) -> None:
        """write provided string to Robonomics datalog"""
        robonomics_bin: str = self.config["path_to_robonomics_file"]
        remote: str = self.config["remote"]
        signature: str = self._context.config["camera"]["key"]
        command: str = f'echo "{data}" | {robonomics_bin} io write datalog {remote} -s {signature}'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

        if process.stdout is not None:
            output = process.stdout.readline()
            transaction_hash: str = output.strip().decode("utf8")
            logging.info(f"Data added to Robonomics datalog. Transaction hash: {transaction_hash}")

    def get(self) -> None:
        raise NotImplementedError


class PinataWorker(BaseIoWorker):
    """Pinata worker handles interactions with Pinata"""

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Pinata cloud")
        self.config: tp.Dict[str, tp.Any] = config["pinata"]

    def post(self, filename: str) -> None:
        logging.info("Pinning file to Pinata in the background")
        pinata_thread = threading.Thread(target=self._pin_to_pinata, args=filename)
        pinata_thread.start()
        logging.info(f"Pinning process started. Thread name: {pinata_thread.name}")

    def _pin_to_pinata(self, filename: str) -> None:
        """pin files in Pinata Cloud to secure their copies in IPFS"""
        api_key = self.config["pinata_api"]
        api_token = self.config["pinata_secret_api"]
        pinata = PinataPy(api_key, api_token)
        logging.info(f"Starting publishing file {filename} to Pinata")
        pinata.pin_file_to_ipfs(filename)
        logging.info(f"File {filename} published to Pinata")

    def get(self) -> None:
        raise NotImplementedError
