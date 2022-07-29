import hashlib
from dataclasses import dataclass


@dataclass
class Employee:
    rfid_card_id: str
    name: str
    position: str
    passport_code: str = ""

    def __post_init__(self) -> None:
        if not self.passport_code:
            self.passport_code = self.get_passport_code()

    @property
    def data(self) -> dict[str, str]:
        return {"name": self.name, "position": self.position}

    def get_passport_code(self) -> str:
        """
        returns encoded employee name to put into the passport

        since unit passport will be published to IPFS, employee name is replaced with
        "employee passport code" - an SHA256 checksum of a string, which is a space-separated
        combination of employee's ID, name and position. since this data is unique for every
        employee, it is safe to assume, that collision is practically impossible.
        """

        employee_passport_string: str = " ".join([self.rfid_card_id, self.name, self.position])
        employee_passport_string_encoded: bytes = employee_passport_string.encode()
        return hashlib.sha256(employee_passport_string_encoded).hexdigest()
