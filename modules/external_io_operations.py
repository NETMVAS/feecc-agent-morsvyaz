import logging
import subprocess
import threading
import typing as tp
from abc import ABC

import ipfshttpclient
from pinatapy import PinataPy

from modules.Types import Config
from modules.VideoEditor import VideoEditor
from modules.short_url_generator import update_short_url


class ExternalIoGateway:
    def __init__(self, config: Config):
        self.config = config
        self.ipfs_hash: tp.Union[str, None] = None

    def send(self, filename: str, keyword: str = "") -> tp.Optional[str]:
        """Handle external IO operations, such as IPFS and Robonomics interactions"""
        if self.config["intro"]["enable"]:
            try:
                filename = VideoEditor.concatenate(
                    filename, delete_source=self.config["general"]["delete_after_record"]
                )  # get concatenated video filename
            except Exception as e:
                logging.error("Failed to concatenate. Error: ", e)

        if self.config["external_io"]["enable"]:
            try:
                worker = IpfsWorker(self, self.config)
                worker.post(filename, keyword)

                if self.config["pinata"]["enable"]:
                    worker = PinataWorker(self, self.config)
                    worker.post(filename)

            except Exception as e:
                logging.error("Error while publishing to IPFS or pinning to pinata. Error: ", e)

        if self.config["datalog"]["enable"] and self.config["external_io"]["enable"]:
            try:
                worker = RobonomicsWorker(self, self.config)
                worker.post()
            except Exception as e:
                logging.error("Error while sending IPFS hash to chain, error: ", e)

            return self.ipfs_hash


class BaseIoWorker(ABC):
    """
    abstract Io worker class for other worker to inherit from
    """

    def __init__(self, context: ExternalIoGateway, target: str) -> None:
        """
        :param context: object of type IoGateway which makes use of the class methods
        """

        logging.debug(f"An instance of {self.name} initialized at {self}")
        self.target: str = target
        self._context: ExternalIoGateway = context

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def post(self, *args, **kwargs) -> None:
        """uploading data to the target"""

        pass

    def get(self, *args, **kwargs) -> None:
        """getting data from the target"""

        pass


class IpfsWorker(BaseIoWorker):
    """IPFS worker handles interactions with IPFS"""

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="IPFS")
        self.config = config

    def post(self, filename: str, keyword: str = "") -> None:
        client = ipfshttpclient.connect()  # establish connection to local external_io node
        res = client.add(filename)  # publish video locally
        self._context.ipfs_hash = res["Hash"]  # get its hash of form Qm....
        logging.info(f"Published to IPFS, hash: {self._context.ipfs_hash}")

        if keyword:
            logging.info("Updating URL")
            update_short_url(keyword, self._context.ipfs_hash, self.config)
            # after publishing file in external_io locally, which is pretty fast,
            # update the link on the qr code so that it redirects now to the gateway with a published file. It may
            # take some for the gateway node to find the file, so we need to pin it in pinata


class RobonomicsWorker(BaseIoWorker):
    """Robonomics worker handles interactions with Robonomics network"""

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Robonomics Network")
        self.config = config["transaction"]

    def post(self) -> None:
        if self._context.ipfs_hash is None:
            raise ValueError(*"ipfs_hash is None")
        program = (
                'echo "'
                + self._context.ipfs_hash
                + '" | '  # send external_io hash
                + self.config["path_to_robonomics_file"]
                + " io write datalog "  # to robonomics chain
                + self.config["remote"]  # specify remote wss, if calling remote node
                + " -s "
                + self._context.config["camera"]["key"]  # sing transaction with camera seed
        )  # line of form  echo "Qm…" | ./robonomics io write datalog -s seed. See robonomics wiki for more
        process = subprocess.Popen(program, shell=True, stdout=subprocess.PIPE)
        output = process.stdout.readline()  # execute the command in shell and wait for it to complete
        logging.info(
            "Published data to chain. Transaction hash is " + output.strip().decode("utf8")
        )  # get transaction hash to use it further if needed


class PinataWorker(BaseIoWorker):
    """Pinata worker handles interactions with Pinata"""

    def __init__(self, context: ExternalIoGateway, config: Config) -> None:
        super().__init__(context, target="Pinata cloud")
        self.config = config["pinata"]

    def post(self, filename: str) -> None:
        logging.info("Camera is sending file to Pinata in the background")

        # create a thread for the function to run in
        pinata_thread = threading.Thread(target=self._pin_to_pinata, args=filename)

        # start the pinning operation
        pinata_thread.start()

    def _pin_to_pinata(self, filename: str) -> None:
        """
        :param filename: full name of a recorded video
        :type filename: str

        pinning files in pinata to make them broadcasted around external_io
        """
        pinata_api = self.config["pinata_api"]  # pinata credentials
        pinata_secret_api = self.config["pinata_secret_api"]
        if pinata_api and pinata_secret_api:
            pinata = PinataPy(pinata_api, pinata_secret_api)
            pinata.pin_file_to_ipfs(
                filename
            )  # here we actually send the entire file to pinata, not just its hash. It will
            # remain the same as if published locally, cause the content is the same.
            logging.info(f"File {filename} published to Pinata")
