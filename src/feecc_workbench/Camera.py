import typing as tp
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from loguru import logger

from .config import config
from .utils import get_headers
from fastapi import Depends

IO_GATEWAY_ADDRESS: str = config.workbench_config.feecc_io_gateway_socket


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

    async def _check_presence(self) -> None:
        """check if self is registered on the backend"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{IO_GATEWAY_ADDRESS}/video/cameras")

        cameras: tp.List[tp.Dict[str, tp.Union[int, str]]] = response.json()["cameras"]

        for camera in cameras:
            if camera["number"] == self.number:
                logger.info("Camera presence check passed")
                return

        raise ValueError(f"Camera with number {self.number} is unknown to the IO gateway")

    async def start(self, headers: tp.Dict[str, str] = Depends(get_headers)) -> None:
        """start the provided record"""
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(
                url=f"{IO_GATEWAY_ADDRESS}/video/camera/{self.number}/start", headers=headers
            )

        if response.is_error:
            raise httpx.RequestError(response.text)

        record_id: str = response.json()["record_id"]
        logger.info(f"Recording {record_id} is started on Camera {self.number}")
        self.record = Record(record_id)

    async def end(self, headers: tp.Dict[str, str] = Depends(get_headers)) -> None:
        """start the provided record"""
        if self.record is None:
            logger.error("There is no ongoing record to end")
            return

        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(
                url=f"{IO_GATEWAY_ADDRESS}/video/record/{self.record.rec_id}/stop",
                headers=headers,
            )

        if response.is_error:
            raise httpx.RequestError(response.text)

        logger.info(f"Recording {self.record.rec_id} is ended on Camera {self.number}")
        self.record.end_time = datetime.now()
        self.record.remote_file_path = response.json()["filename"]
