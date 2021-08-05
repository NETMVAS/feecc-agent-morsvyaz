from __future__ import annotations

import logging
import os
import subprocess
import time
import typing as tp

from ._external_io_operations import File


class Camera:
    def __init__(self, config: tp.Dict[str, str]) -> None:
        """
        :param config: dictionary containing all the configurations
        :type config: dict

        Class description. On initiating state some attributes and methods to be described below
        """
        self.ip: str = config["ip"]  # dictionary containing all the configurations
        self.port: str = config["port"]  # port where the camera streams, required for rtsp
        self.login: str = config["login"]  # camera login to obtain access to the stream
        self.password: str = config["password"]  # camera password to obtain access to the stream
        # List of Recording objects each corresponding to an ongoing recording process
        self._ongoing_records: tp.List[Recording] = []

    def start_record(self, unit_uuid: str) -> None:
        """start recording video"""
        recording = Recording(self, unit_uuid)
        self._ongoing_records.append(recording)
        o_r = self._ongoing_records
        logging.debug(
            f"current ongoing records list ({len(o_r)} items) is {[r.file.filename for r in o_r]}"
        )

    def stop_record(self) -> tp.Optional[File]:
        """stop recording a video for the requested unit"""
        recording = self._ongoing_records.pop(0) if self._ongoing_records else None
        logging.debug(f"Trying to stop record for {recording}")
        if not recording:
            logging.error("Could not stop record for unit: no ongoing record found")
            return None

        file = recording.stop()
        logging.info("Stopped record for unit")
        return file


class Recording:
    """a recording object represents one ongoing recording process"""

    def __init__(self, camera: Camera, unit_uuid: str) -> None:
        self._camera: Camera = camera
        self.unit_uuid: str = unit_uuid
        self.recording_ongoing: bool = False  # current status
        self.process_ffmpeg: tp.Optional[subprocess.Popen] = None  # type: ignore
        logging.debug(f"New Recording object initialized at {self}")
        self.file: File = File(self._start_record())

    def _toggle_record_flag(self) -> None:
        self.recording_ongoing = not self.recording_ongoing

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
        dir_ = "output/video"

        if not os.path.isdir(dir_):
            os.mkdir(dir_)

        filename = f"{dir_}/unit_{unit_uuid}_assembly_video_1.mp4"

        # determine a valid video name not to override an existing video
        cnt = 1
        while os.path.exists(filename):
            filename.replace(f"video_{cnt}", f"video_{cnt + 1}")
            cnt += 1

        self._execute_ffmpeg(filename)
        self._toggle_record_flag()

        return filename

    def stop(self) -> File:
        """stop recording a video"""
        if self.process_ffmpeg and self.recording_ongoing:
            self.process_ffmpeg.terminate()  # kill the subprocess to liberate system resources
            logging.info(f"Finished recording video for unit {self.unit_uuid}")
            self._toggle_record_flag()
            time.sleep(1)  # some time to finish the process

        return self.file

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
