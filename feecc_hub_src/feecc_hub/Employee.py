import hashlib
import typing as tp
from dataclasses import dataclass

from loguru import logger


@dataclass(frozen=True)
class Employee:
    rfid_card_id: str
    name: str
    position: str

    def __post_init__(self) -> None:
        logger.debug(f"Initialized Employee with id {self.rfid_card_id}, data: {self.data}")

    @property
    def data(self) -> tp.Dict[str, str]:
        data = {"name": self.name, "position": self.position}
        return data

    @property
    def passport_code(self) -> str:
        """
        returns encoded employee name to put into the passport

        since unit passport will be published to IPFS, employee name is replaced with
        "employee passport code" - an SHA256 checksum of a string, which is a space-separated
        combination of employee's ID, name and position. since this data is unique for every
        employee, it is safe to assume, that collision is practically impossible.
        """

        employee_passport_string: str = " ".join([self.rfid_card_id, self.name, self.position])
        employee_passport_string_encoded: bytes = employee_passport_string.encode()
        employee_passport_code: str = hashlib.sha256(employee_passport_string_encoded).hexdigest()
        return employee_passport_code
