import typing as tp
import csv
import logging


# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="agent.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)


class Employee:
    def __init__(self):
        self.employee_db_path: str = "employee_db.csv"

    def validate_employee(self):
        pass

    @staticmethod
    def find_in_db(employee_id: str, db_path: str = "employee_db.csv") -> tp.List[str]:
        """:returns employee data, incl. name, position and employee ID if employee found in DB"""

        employee_data = []

        # open employee database
        try:
            with open(db_path, "r") as file:
                reader = csv.reader(file)

                # look for employee in the db
                for row in reader:
                    if employee_id in row:
                        employee_data = row
                        break
        except FileNotFoundError:
            logging.critical(f"File '{db_path}' is not in the working directory, cannot retrieve employee data")

        return employee_data
