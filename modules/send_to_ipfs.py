import ipfshttpclient
import logging
import os
import subprocess
import typing as tp
import threading

from pinatapy import PinataPy
from modules.short_url_generator import update_short_url

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="agent.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)


class IPFSWorker:

    def __init__(self, config: tp.Dict[str, tp.Dict[str, tp.Any]]):
        self.config = config
        self.ipfs_hash: tp.Optional[str] = None

    @staticmethod
    def concatenate(dirname: str, filename: str) -> str:
        """
        :param dirname: path to the project ending with .../cameras_robonomics
        :type dirname: str
        :param filename: full name of a recorded video
        :type filename: str
        :return: full name of a new video (concatenated with intro)
        :rtype: str

        concatenating two videos (intro with a main video) if needed. Intro is to be placed in media folder. More in config
        file
        """
        logging.info("Concatenating videos")
        if not os.path.exists(dirname + "/media/intro.mp4"):
            raise Exception("Intro file doesn't exist!")
        concat_string = "file \'" + dirname + "/media/intro.mp4\'\nfile \'" + filename + "\'"
        # it should look like:
        #   file './media/intro.mp4'
        #   file './media/vid.mp4'
        with open(dirname + "/output/vidlist.txt", "w") as text_file:
            text_file.write(concat_string)
            text_file.close()  # create txt file
        concat_filename = filename[:-4] + "_intro" + filename[
                                                     -4:]  # new file will have another name to detect concatenated
        # videos
        concat_command = (
                "ffmpeg -f concat -safe 0 -i "
                + dirname
                + "/output/vidlist.txt -c copy "
                + concat_filename
        )  # line looks like: ffmpeg -f concat -safe 0 -i vidlist.txt -c copy output.mp4. More on ffmpeg.org
        concat_process = subprocess.Popen(
            "exec " + concat_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )  # subprocess to execute ffmpeg utility command in shell and obtain all the flows
        concat_process.stdout.readline()  # wait till the process finishes
        return concat_filename  # return new filename

    def pin_to_pinata(self, filename: str) -> None:
        """
        :param filename: full name of a recorded video
        :type filename: str

        pinning files in pinata to make them broadcasted around ipfs
        """
        pinata_api = self.config["pinata"]["pinata_api"]  # pinata credentials
        pinata_secret_api = self.config["pinata"]["pinata_secret_api"]
        if pinata_api and pinata_secret_api:
            pinata = PinataPy(pinata_api, pinata_secret_api)
            pinata.pin_file_to_ipfs(
                filename)  # here we actually send the entire file to pinata, not just its hash. It will
            # remain the same as if published locally, cause the content is the same.
            logging.info("File published to Pinata")

    def send(self, filename: str, keyword: str = "", qrpic: str = "") -> str:
        """
        :param filename: full name of a recorded video
        :type filename: str
        :param keyword: shorturl keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
        :type keyword: str
        :param qrpic: name of a qr-code file. Qr-code, which is redirecting to IPFS gateway
        :type qrpic: str

        concatenate if needed, publish files to ipfs locally, send them to pinata, push hashes to robonomics
        """
        if self.config["intro"]["enable"]:
            try:
                non_concatenated_filename = filename  # save old filename to delete if later
                filename = filename  # get concatenated video filename
            except Exception as e:
                logging.error("Failed to concatenate. Error: ", e)

        if self.config["ipfs"]["enable"]:
            try:
                self.ipfs_push(filename, keyword)

                if self.config["pinata"]["enable"]:
                    self.pinata_push(filename)

            except Exception as e:
                logging.error(
                    "Error while publishing to IPFS or pinning to pinata. Error: ", e
                )

        if self.config["general"]["delete_after_record"] and qrpic:
            try:
                self.clean_after_record(filename, qrpic, non_concatenated_filename)
            except Exception as e:
                logging.error("Error while deleting file, error: ", e)

        if self.config["datalog"]["enable"] and self.config["ipfs"]["enable"]:
            try:
                self.datalog_push()
            except Exception as e:
                logging.error("Error while sending IPFS hash to chain, error: ", e)

            return self.ipfs_hash

    def ipfs_push(self, filename: str, keyword: str) -> None:
        client = ipfshttpclient.connect()  # establish connection to local ipfs node
        res = client.add(filename)  # publish video locally
        self.ipfs_hash = res["Hash"]  # get its hash of form Qm....
        logging.info("Published to IPFS, hash: " + self.ipfs_hash)

        if keyword:
            logging.info("Updating URL")
            update_short_url(keyword, self.ipfs_hash, self.config)
            # after publishing file in ipfs locally, which is pretty fast,
            # update the link on the qr code so that it redirects now to the gateway with a published file. It may
            # take some for the gateway node to find the file, so we need to pin it in pinata

    def pinata_push(self, filename: str) -> None:
        logging.info("Camera is sending file to Pinata in the background")

        # create a thread for the function to run in
        pinata_thread = threading.Thread(
            target=self.pin_to_pinata,
            args=filename
        )

        # start the pinning operation
        pinata_thread.start()

    def clean_after_record(self, filename: str, qrpic: str, non_concatenated_filename: str):
        logging.info("Removing files")
        os.remove(filename)
        os.remove(qrpic)
        if self.config["intro"]["enable"]:
            os.remove(non_concatenated_filename)  # liberate free space. delete both concatenated and initial files

    def datalog_push(self) -> None:
        if self.ipfs_hash is None:
            raise ValueError(*"ipfs_hash is None")
        program = (
                'echo \"' + self.ipfs_hash + '\" | '  # send ipfs hash
                + self.config["transaction"]["path_to_robonomics_file"] + " io write datalog "  # to robonomics chain
                + self.config["transaction"]["remote"]  # specify remote wss, if calling remote node
                + " -s "
                + self.config["camera"]["key"]  # sing transaction with camera seed
        )  # line of form  echo "Qm…" | ./robonomics io write datalog -s seed. See robonomics wiki for more
        process = subprocess.Popen(program, shell=True, stdout=subprocess.PIPE)
        output = process.stdout.readline()  # execute the command in shell and wait for it to complete
        logging.info(
            "Published data to chain. Transaction hash is "
            + output.strip().decode("utf8")
        )  # get transaction hash to use it further if needed
