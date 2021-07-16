import logging
import os
import subprocess
import threading
import typing as tp
from abc import ABC, abstractmethod

import ipfshttpclient
from pinatapy import PinataPy

from ._Types import Config
from ._short_url_generator import update_short_url


class File:
    """stores data about one file-like entity with related attributes"""

    def __init__(self, path: str) -> None:
        if not os.path.exists(path):
            message = f"Path {path} doesn't point to an actual file"
            logging.error(message)
            raise FileNotFoundError(message)

        self.path: str = path
        self.filename: str = os.path.basename(self.path)
        self.ipfs_hash: tp.Optional[str] = None
        self.is_pinned: bool = False
        self.short_url: tp.Optional[str] = None
        self.qrcode: tp.Optional[str] = None

    @property
    def keyword(self) -> tp.Optional[str]:
        if self.short_url is None:
            return None
        else:
            return self.short_url.split("/")[-1]

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

            if file.keyword and file.ipfs_hash:
                logging.info(f"Updating URL {file.short_url}")
                update_short_url(file.keyword, file.ipfs_hash, self.config)

            if self.config["pinata"]["enable"]:
                pinata_worker = PinataWorker(self, self.config)
                pinata_worker.post(file)

        if self.config["datalog"]["enable"] and file.ipfs_hash:
            try:
                robonomics_worker = RobonomicsWorker(self, self.config)
                robonomics_worker.post(file.ipfs_hash)
            except Exception as e:
                logging.error(f"Error writing IPFS hash to Robonomics datalog: {e}")

            return file.ipfs_hash

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

    def post(self, file: File) -> None:
        """publish file on IPFS"""
        ipfs_client = ipfshttpclient.connect()
        result = ipfs_client.add(file.filename)
        ipfs_hash: str = result["Hash"]
        logging.info(f"File {file.filename} published to IPFS, hash: {ipfs_hash}")
        file.ipfs_hash = ipfs_hash

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

    def post(self, file: File) -> None:
        logging.info("Pinning file to Pinata in the background")
        pinata_thread = threading.Thread(target=self._pin_to_pinata, args=(file,))
        pinata_thread.start()
        logging.info(f"Pinning process started. Thread name: {pinata_thread.name}")

    def _pin_to_pinata(self, file: File) -> None:
        """pin files in Pinata Cloud to secure their copies in IPFS"""
        api_key = self.config["pinata_api"]
        api_token = self.config["pinata_secret_api"]
        pinata = PinataPy(api_key, api_token)
        logging.info(f"Starting publishing file {file.filename} to Pinata")
        pinata.pin_file_to_ipfs(file.path)
        logging.info(f"File {file.filename} published to Pinata")

    def get(self) -> None:
        raise NotImplementedError
