import logging
import subprocess
import threading
import typing as tp
from abc import ABC, abstractmethod

import ipfshttpclient
from pinatapy import PinataPy

from ._Types import Config
from ._VideoEditor import VideoEditor
from ._short_url_generator import update_short_url


class ExternalIoGateway:
    def __init__(self, config: Config):
        self.config: Config = config
        self.ipfs_hash: tp.Optional[str] = None

    def send(self, filename: str, keyword: str = "") -> tp.Optional[str]:
        """Handle external IO operations, such as IPFS and Robonomics interactions"""
        if self.config["intro"]["enable"]:
            try:
                filename = VideoEditor.concatenate(
                    filename, delete_source=bool(self.config["general"]["delete_after_record"])
                )  # get concatenated video filename
            except Exception as e:
                logging.error("Failed to concatenate. Error: ", e)

        if self.config["ipfs"]["enable"]:
            try:
                ipfs_worker = IpfsWorker(self, self.config)
                ipfs_worker.post(filename, keyword)

                if self.config["pinata"]["enable"]:
                    pinata_worker = PinataWorker(self, self.config)
                    pinata_worker.post(filename)

            except Exception as e:
                logging.error(f"Error while publishing to IPFS or pinning to pinata. Error: {e}")

        if self.config["datalog"]["enable"] and self.config["ipfs"]["enable"]:
            try:
                robonomics_worker = RobonomicsWorker(self, self.config)
                robonomics_worker.post()
            except Exception as e:
                logging.error(f"Error while sending IPFS hash to chain, error: {e}")

            return self.ipfs_hash

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

    def post(self, filename: str, keyword: tp.Optional[str] = None) -> None:
        """share file on IPFS"""
        ipfs_client = ipfshttpclient.connect()
        result = ipfs_client.add(filename)
        self._context.ipfs_hash = result["Hash"]
        logging.info(f"File {filename} published to IPFS, hash: {self._context.ipfs_hash}")

        if keyword is not None:
            logging.info(f"Updating URL with keyword {keyword}")

            if self._context.ipfs_hash is None:
                raise ValueError("Context IPFS hash is None")

            update_short_url(keyword, self._context.ipfs_hash, self.config)

    def get(self) -> None:
        raise NotImplementedError


class RobonomicsWorker(BaseIoWorker):
    """Robonomics worker handles interactions with Robonomics network"""

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Robonomics Network")
        self.config: tp.Dict[str, tp.Any] = config["transaction"]

    def post(self) -> None:
        if self._context.ipfs_hash is None:
            raise ValueError("ipfs_hash is None")

        ipfs_hash: str = self._context.ipfs_hash
        robonomics_bin: str = self.config["path_to_robonomics_file"]
        remote: str = self.config["remote"]
        signature: str = self._context.config["camera"]["key"]
        command: str = f'echo "{ipfs_hash}" | {robonomics_bin} io write datalog {remote} -s {signature}'
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)

        if process.stdout is None:
            raise ValueError("Popen process stdout is None")

        output = process.stdout.readline()
        transaction_hash: str = output.strip().decode("utf8")
        logging.info(f"Data written to Robonomics datalog. Transaction hash: {transaction_hash}")

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
