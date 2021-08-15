from __future__ import annotations

import os
import subprocess
import typing as tp
from collections import deque

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
        # List of Recording objects each corresponding to an ongoing recording process
        self._ongoing_records: tp.Deque[Recording] = deque()

    def start_record(self, unit_uuid: str) -> None:
        """start recording video"""
        recording = Recording(self, unit_uuid)
        self._ongoing_records.append(recording)
        self._debug_ongoing_records(method="start_record")

    def stop_record(self) -> tp.Optional[File]:
        """stop recording a video for the requested unit"""
        self._debug_ongoing_records(method="stop_record")
        recording = self._ongoing_records.popleft() if self._ongoing_records else None
        logger.debug(f"Trying to stop record for {recording}")

        if not recording:
            logger.error("Could not stop record for unit: no ongoing record found")
            return None

        video_record: File = recording.stop()
        logger.info(f"Stopped recording video {video_record.filename}")
        return video_record

    def _debug_ongoing_records(self, method: str) -> None:
        o_r = self._ongoing_records
        logger.debug(
            f"Operation: {method}. Current ongoing records list ({len(o_r)} items) is {[r.file.filename for r in o_r]}"
        )


class Recording:
    """a recording object represents one ongoing recording process"""

    def __init__(self, camera: Camera, unit_uuid: str) -> None:
        self._camera: Camera = camera
        self._unit_uuid: str = unit_uuid
        self._process_ffmpeg: tp.Optional[subprocess.Popen] = None  # type: ignore
        self.file: File = File(self._start_record())

    @property
    def is_ongoing(self) -> bool:
        return self._process_ffmpeg is not None and self._process_ffmpeg.poll() is None

    def _start_record(self) -> str:
        """start a record and return future video filename"""
        unit_uuid: str = self._unit_uuid
        logger.info(f"Recording started for the unit with UUID {unit_uuid}")
        dir_: str = "output/video"
        if not os.path.isdir(dir_):
            os.mkdir(dir_)
        filename = f"{dir_}/unit_{unit_uuid}_assembly_video_1.mp4"

        # determine a valid video name not to override an existing video
        cnt: int = 1
        while os.path.exists(filename):
            filename = filename.replace(f"video_{cnt}", f"video_{cnt + 1}")
            cnt += 1

        self._execute_ffmpeg(filename)
        return filename

    def stop(self) -> File:
        """stop recording a video"""
        if self.is_ongoing and self._process_ffmpeg is not None:
            self._process_ffmpeg.terminate()  # kill the subprocess to liberate system resources
            logger.info(f"Finished recording video for unit {self._unit_uuid}")

        return self.file

    def _execute_ffmpeg(self, filename: str) -> None:
        """Execute ffmpeg command"""
        # ffmpeg -rtsp_transport tcp -i "rtsp://login:password@ip:port/Streaming/Channels/101" -c copy -map 0 vid.mp4
        cam: Camera = self._camera
        command: str = f'ffmpeg -rtsp_transport tcp -i "rtsp://{cam.login}:{cam.password}@{cam.ip}:{cam.port}/Streaming/Channels/101" -r 25 -c copy -map 0 {filename}'
        self._process_ffmpeg = subprocess.Popen(command, shell=True)
        logger.info(f"Started recording video '{filename}' using ffmpeg")
