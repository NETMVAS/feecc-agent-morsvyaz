from __future__ import annotations

import os
import subprocess
import typing as tp

from loguru import logger

from ._external_io_operations import File
from .Types import ConfigSection


class Camera:
    """a wrapper for the video camera"""

    def __init__(self, config: ConfigSection) -> None:
        self.ip: str = config["ip"]  # dictionary containing all the configurations
        self.port: str = config["port"]  # port where the camera streams, required for rtsp
        self.login: str = config["login"]  # camera login to obtain access to the stream
        self.password: str = config["password"]  # camera password to obtain access to the stream
        self.record: tp.Optional[Recording] = None  # current ongoing record

    def start_record(self, unit_uuid: str) -> None:
        """start recording video"""
        self.record = Recording(self, unit_uuid)

    def stop_record(self) -> tp.Optional[Recording]:
        """stop recording a video for the requested unit"""
        logger.warning("target 5 reached")
        logger.debug(f"Trying to stop record for {self.record.filename}")
        if not self.record:
            logger.error("Could not stop record for unit: no ongoing record found")
            return None
        self.record.stop()
        logger.warning("target 6 reached")
        logger.info(f"Stopped recording video {self.record.filename}")
        return self.record


class Recording(File):
    """a recording object represents one ongoing recording process"""

    def __init__(self, camera: Camera, unit_uuid: str) -> None:
        self._camera: Camera = camera
        self._unit_uuid: str = unit_uuid
        self._process_ffmpeg: tp.Optional[subprocess.Popen] = None  # type: ignore
        super().__init__(self._get_filename(unit_uuid))
        self._start_record()

    @property
    def is_ongoing(self) -> bool:
        return self._process_ffmpeg is not None and self._process_ffmpeg.poll() is None

    def _start_record(self) -> None:
        """start a record and return future video filename"""
        logger.info(f"Recording started for the unit with UUID {self._unit_uuid}")
        self._execute_ffmpeg(self.path)

    @staticmethod
    def _get_filename(unit_uuid: str, dir_: str = "output/video") -> str:
        """determine a valid video name not to override an existing video"""
        if not os.path.isdir(dir_):
            os.mkdir(dir_)
        filename = f"{dir_}/unit_{unit_uuid}_assembly_video_1.mp4"
        cnt: int = 1
        while os.path.exists(filename):
            filename = filename.replace(f"video_{cnt}", f"video_{cnt + 1}")
            cnt += 1
        return filename

    def stop(self) -> None:
        """stop recording a video"""
        if self.is_ongoing and self._process_ffmpeg is not None:
            self._process_ffmpeg.terminate()  # kill the subprocess to liberate system resources
            logger.info(f"Finished recording video for unit {self._unit_uuid}")

    def _execute_ffmpeg(self, filename: str) -> None:
        """Execute ffmpeg command"""
        # ffmpeg -rtsp_transport tcp -i "rtsp://login:password@ip:port/Streaming/Channels/101" -c copy -map 0 vid.mp4
        cam: Camera = self._camera
        command: str = f'ffmpeg -rtsp_transport tcp -i "rtsp://{cam.login}:{cam.password}@{cam.ip}:{cam.port}/Streaming/Channels/101" -r 25 -c copy -map 0 {filename}'
        self._process_ffmpeg = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )
        logger.info(f"Started recording video '{filename}' using ffmpeg")
