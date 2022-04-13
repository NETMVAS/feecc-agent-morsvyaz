import typing as tp
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from loguru import logger

from .config import Config
from .utils import get_headers

CAMERAMAN_ADDRESS: str = Config.camera.cameraman_uri


@dataclass
class Record:
    rec_id: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: tp.Optional[datetime] = None
    remote_file_path: tp.Optional[str] = None

    @property
    def is_ongoing(self) -> bool:
        return self.start_time is not None and self.end_time is None


class Camera:
    """a gateway to interact with the external video camera"""

    def __init__(self, number: int) -> None:
        self.number: int = number
        self.record: tp.Optional[Record] = None
        self._check_presence()

    def _check_presence(self) -> None:
        """check if self is registered on the backend"""
        try:
            response = httpx.get(f"{CAMERAMAN_ADDRESS}/cameras")
        except httpx.ConnectError:
            logger.critical("GW connection has been refused. Is it up?")
            return

        cameras: tp.List[tp.Dict[str, tp.Union[int, str]]] = response.json()["cameras"]

        for camera in cameras:
            if camera["number"] == self.number:
                logger.info("Camera presence check passed")
                return

        raise ValueError(f"Camera with number {self.number} is unknown to the IO gateway")

    async def start(self, rfid_card_id: str) -> None:
        """start the provided record"""
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(
                url=f"{CAMERAMAN_ADDRESS}/camera/{self.number}/start", headers=get_headers(rfid_card_id)
            )

        if response.is_error:
            raise httpx.RequestError(response.text)

        record_id: str = response.json()["record_id"]
        logger.info(f"Recording {record_id} is started on Camera {self.number}")
        self.record = Record(record_id)

    async def end(self, rfid_card_id: str) -> None:
        """start the provided record"""
        if self.record is None:
            logger.error("There is no ongoing record to end")
            return

        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(
                url=f"{CAMERAMAN_ADDRESS}/record/{self.record.rec_id}/stop",
                headers=get_headers(rfid_card_id),
            )

        if response.is_error:
            raise httpx.RequestError(response.text)

        logger.info(f"Recording {self.record.rec_id} is ended on Camera {self.number}")
        self.record.end_time = datetime.now()
        self.record.remote_file_path = response.json()["filename"]
