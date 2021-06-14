import typing as tp
import csv
import logging
import io


class Employee:
    def __init__(self, rfid_card_id: str) -> None:
        self.id: str = rfid_card_id
        self.employee_db_entry: tp.List[str] = self._find_in_db(rfid_card_id)
        self.name: str = self.employee_db_entry[1]
        self.position: str = self.employee_db_entry[2]

    @property
    def is_logged_in(self) -> bool:
        return not self.id == ""

    @property
    def data(self) -> tp.Dict[str, str]:
        data = {
            "name": self.name,
            "position": self.position
        }

        return data

    @staticmethod
    def _find_in_db(employee_card_id: str, db_path: str = "config/employee_db.csv") -> tp.Optional[tp.List[str]]:
        """
        Method is used to get employee data (or confirm its absence)

        Args:
            employee_card_id (str): Employee card rfid data
            db_path (str): Optional argument. Path to employee db

        Returns:
            None if employee not found, if found returns list with full name and position.
        """

        employee_data: tp.Optional[tp.List[str]] = None

        # open employee database
        try:
            with io.open(db_path, "r", encoding="utf-8") as file:
                reader = csv.reader(file)

                # look for employee in the db
                for row in reader:
                    if employee_card_id in row:
                        employee_data = row
                        break
        except FileNotFoundError:
            logging.critical(f"File '{db_path}' is not in the working directory, cannot retrieve employee data")

        if employee_data is None:
            logging.error(f"Employee with card id {employee_card_id} not found. Access denied.")

        return employee_data
