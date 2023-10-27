import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from loguru import logger
import socket
from .config import CONFIG
from .Messenger import messenger
import re
from .translation import translation

MINIMAL_RECORD_DURATION_SEC: int = 3


@dataclass
class Record:
    """a recording object represents one ongoing recording process"""

    filename: str | None = None
    process_ffmpeg: asyncio.subprocess.Process | None = None
    record_id: str = field(default_factory=lambda: uuid4().hex)
    start_time: datetime | None = None
    end_time: datetime | None = None

    def __post_init__(self) -> None:
        self.filename = self._get_video_filename()

    def __len__(self) -> int:
        """calculate recording duration in seconds"""
        if self.start_time is None:
            return 0

        if self.end_time is not None:
            duration = self.end_time - self.start_time
        else:
            duration = datetime.now() - self.start_time

        return int(duration.total_seconds())

    def _get_video_filename(self, dir_: str = "output/video") -> str:
        """determine a valid video name not to override an existing video"""
        if not os.path.isdir(dir_):
            os.makedirs(dir_)
        return f"{dir_}/{self.record_id}.mp4"

    @property
    def is_ongoing(self) -> bool:
        """
        Whether record is ongoing
        """
        return self.start_time is not None and self.end_time is None

    @logger.catch(reraise=True)
    async def start(self) -> None:
        """Execute ffmpeg command"""
        # ffmpeg -loglevel warning -rtsp_transport tcp -i "rtsp://login:password@ip:port/Streaming/Channels/101" \
        # -c copy -map 0 vid.mp4
        command = CONFIG.camera.ffmpeg_command
        command = command.replace("FILENAME", str(self.filename), 1)

        self.process_ffmpeg = await asyncio.subprocess.create_subprocess_shell(
            cmd=command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        self.start_time = datetime.now()
        logger.info(f"Started recording video '{self.filename}' using ffmpeg. {self.process_ffmpeg.pid=}")

    @logger.catch(reraise=True)
    async def stop(self) -> None:
        """stop recording a video"""
        if self.process_ffmpeg is None:
            logger.error(f"Failed to stop record {self.record_id}")
            logger.debug(f"Operation ongoing: {self.is_ongoing}, ffmpeg process: {bool(self.process_ffmpeg)}")
            return

        if len(self) < MINIMAL_RECORD_DURATION_SEC:
            logger.warning(
                f"Recording {self.record_id} duration is below allowed minimum ({MINIMAL_RECORD_DURATION_SEC=}s). "
                "Waiting for it to reach it before stopping."
            )
            await asyncio.sleep(MINIMAL_RECORD_DURATION_SEC - len(self))

        logger.info(f"Trying to stop record {self.record_id} process {self.process_ffmpeg.pid=}")

        stdout, stderr = await self.process_ffmpeg.communicate(input=b"q")
        await self.process_ffmpeg.wait()
        return_code = self.process_ffmpeg.returncode

        if return_code == 0:
            logger.debug("Got a zero return code from ffmpeg subprocess. Assuming success.")
        else:
            logger.error(f"Got a non zero return code from ffmpeg subprocess: {return_code}")
            logger.debug(f"{stdout=} {stderr=}")

        self.process_ffmpeg = None
        self.end_time = datetime.now()

        logger.info(f"Finished recording video for record {self.record_id}")


class Camera:
    """A module to interact with a local IP camera"""

    def __init__(self) -> None:
        self.record: Record | None = None
        self._is_up()

    @staticmethod
    def _is_up() -> bool:
        """Check if camera is connected to the workbench computer"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.25)
            pattern: re.Pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d{1,5}')
            addr, port = pattern.search(CONFIG.camera.ffmpeg_command)[0].split(":")
            s.connect((addr, int(port)))
            logger.debug("Camera is up")
            return True
        except Exception as e:
            logger.error(f"No response from camera. Is it up? Error: {e}")
            messenger.error(translation('NoConnection'))
            return False

    async def start_record(self) -> None:
        """start the provided record"""
        self.record = Record()

        try:
            if not self._is_up():
                raise BrokenPipeError("Camera is unreachable")
            await self.record.start()
            logger.info(f"Recording {self.record.record_id} has started.")
        except Exception as e:
            logger.error(f"Failed to start recording. Error: {e}")
            messenger.error(translation('ErrorRecording'))
            return

    async def end_record(self) -> None:
        """start the provided record"""

        try:
            if not self.record.is_ongoing:
                raise ValueError("Recording is not currently ongoing thus cannot be stopped")
            await self.record.stop()
            logger.info(f"Stopped recording video for recording {self.record.record_id}")
        except Exception as e:
            logger.error(f"Failed to stop recording. Error: {e}")
            return
