import csv
import logging
import subprocess
import time
import typing as tp
from os import path


class Camera:
    def __init__(self, config: tp.Dict[str, str]) -> None:
        """
        :param config: dictionary containing all the configurations
        :type config: dict

        Class description. On initiating state some attributes and methods to be described below
        """
        self.qrpic = None  # future path to qr-code picture file. This will be used to create a labels
        self.keyword = None  # shorturl keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
        self.ip = config["ip"]  # dictionary containing all the configurations
        self.port = config["port"]  # port where the camera streams, required for rtsp
        self.login = config["login"]  # camera login to obtain access to the stream
        self.password = config["password"]  # camera password to obtain access to the stream
        self._ongoing_records = []  # List of Recording objects each corresponding to an ongoing recording process

    def start_record(self, unit_uuid: str) -> None:
        """start recording video"""

        recording = Recording(self, unit_uuid)
        self._ongoing_records.append(recording)

    def stop_record(self, unit_uuid: str) -> str:
        """stop recording a video for the requested unit"""

        recording = None

        for rec in self._ongoing_records:
            if rec.unit_uuid == unit_uuid:
                recording = rec
                self._ongoing_records.remove(rec)
                break

        if not recording:
            logging.error(f"Could not stop record for unit {unit_uuid}: no ongoing record for this unit found")
            return ""

        filename = recording.stop_record()
        logging.info(f"Stopped record for unit {unit_uuid}")
        return filename

    @staticmethod
    def match_camera_with_table(camera_id: int, table_path: str = "config/camera_table.csv") -> tp.Optional[tp.Dict[str, str]]:
        logging.debug(f"Looking for camera with ID {camera_id} in {table_path}")
        with open(table_path, "r") as f:
            reader = csv.reader(f, delimiter=";")
            for table_id, ip, port, login, password in reader:
                if table_id == camera_id:
                    data_entry = {"ip": ip, "port": port, "login": login, "password": password}
                    logging.debug(f"Found an entry for camera {camera_id} in {table_path}:\n{data_entry}")
                    return data_entry

        logging.error(f"Could not find an entry for camera {camera_id} in {table_path}")


class Recording:
    """a recording object represents one ongoing recording process"""

    def __init__(self, camera: Camera, unit_uuid: str) -> None:
        self._camera = camera
        self.unit_uuid: str = unit_uuid
        self.recording_ongoing: bool = False  # current status
        self.process_ffmpeg = None  # popen object o ffmpeg subprocess
        logging.debug(f"New Recording object initialized at {self}")
        self._start_record()

    def _start_record(self) -> str:
        """
        unit_uuid: UUID of a unit passport associated with a unit, which assembly
        process is being recorded by the camera

        main method to record video from camera. Uses popen and ffmpeg utility

        :returns: saved video relative path
        """

        unit_uuid: str = self.unit_uuid
        logging.info(f"Recording started for the unit with UUID {unit_uuid}")

        # new video filepath. It is to be saved in a separate directory
        # with a UUID and number in case a unit has more than one video associated with it
        filename = f"output/unit_{unit_uuid}_assembly_video_1.mp4"

        # determine a valid video name not to override an existing video
        cnt = 1
        while path.exists(filename):
            filename.replace(f"video_{cnt}", f"video_{cnt + 1}")
            cnt += 1

        self._execute_ffmpeg(filename)

        return filename

    def stop_record(self) -> None:
        """stop recording a video"""

        if self.process_ffmpeg and self.recording_ongoing:
            self.process_ffmpeg.terminate()  # kill the subprocess to liberate system resources
            logging.info(f"Finished recording video for unit {self.unit_uuid}")
            self.recording_ongoing = False
            time.sleep(1)  # some time to finish the process

    def _execute_ffmpeg(self, filename: str) -> None:
        """Execute ffmpeg command"""
        program_ffmpeg = f'ffmpeg -rtsp_transport tcp -i "rtsp://{self._camera.login}:{self._camera.password}@{self._camera.ip}:\
{self._camera.port}/Streaming/Channels/101" -r 25 -c copy -map 0 {filename}'

        # the entire line looks like
        # ffmpeg -rtsp_transport tcp -i "rtsp://login:password@ip:port/Streaming/Channels/101" -c copy -map 0 vid.mp4
        # more on ffmpeg.org
        self.process_ffmpeg = subprocess.Popen(
            "exec " + program_ffmpeg,
            shell=True,  # execute in shell
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,  # to get access to all the flows
        )
        logging.info(f"Started recording video '{filename}' using ffmpeg")
