import logging
import typing as tp

from flask import Flask, Response, request
from flask_restful import Api, Resource

from modules.Hub import Hub
from modules.Unit import Unit
from modules.WorkBench import WorkBench

# set up logging
logging.basicConfig(
    level=logging.INFO, filename="agent.log", format="%(asctime)s %(levelname)s: %(message)s"
)

# global variables
hub = Hub()
app = Flask(__name__)
api = Api(app)


# REST API request handlers

# Unit operations handling
class UnitCreationHandler(Resource):
    """handle new Unit creation"""

    @staticmethod
    def post() -> Response:
        try:
            workbench_no: int = request.get_json()["workbench_no"]
            logging.debug(f"Received a request to create a new Unit from workbench no. {workbench_no}")

        except Exception as E:
            logging.error(f"Can't handle the request. Request payload: {request.get_json()}. Exception occurred:\n{E}")
            return Response(status=500)

        global hub

        try:
            new_unit_internal_id: str = hub.create_new_unit()
            response = {
                "status": True,
                "comment": "New unit created successfully",
                "unit_internal_id": new_unit_internal_id
            }
            logging.info(f"Initialized new unit with internal ID {new_unit_internal_id}")
            return Response(response=response, status=200)

        except Exception as E:
            logging.error(f"Exception occurred while creating new Unit:\n{E}")
            response = {
                "status": False,
                "comment": "Could not create a new Unit. Internal error occurred",
            }
            return Response(response=response, status=500)


class UnitStartRecordHandler(Resource):
    """handle start recording operation on a Unit"""

    @staticmethod
    def post(unit_internal_id: str) -> Response:
        global hub
        request_payload: tp.Dict[str, tp.Any] = request.get_json()

        try:
            workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
            unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)
            workbench.start_operation(unit, request_payload["production_stage_name"],
                                      request_payload["additional_info"])
            message = f"Started operation '{request_payload['production_stage_name']}' on Unit {unit_internal_id} at " \
                      f"Workbench no. {request_payload['workbench_no']} "
            response_data = {
                "status": True,
                "comment": message
            }
            logging.info(message)
            return Response(status=200, response=response_data)

        except Exception as E:
            message = f"Couldn't handle request. An error occurred: {E}"
            logging.error(message)
            logging.debug(request_payload)
            response_data = {
                "status": False,
                "comment": message
            }
            return Response(response=response_data, status=500)


# todo
class UnitEndRecordHandler(Resource):
    """handle end recording operation on a Unit"""


# todo
class UnitUploadHandler(Resource):
    """handle Unit lifecycle end"""


# Employee operations handling
# todo
class EmployeeLogInHandler(Resource):
    """handle logging out the Employee at a given Workbench"""


# todo
class EmployeeLogOutHandler(Resource):
    """handle logging out the Employee at a given Workbench"""


# Employee operations handling
class WorkBenchStatusHandler(Resource):
    """handle providing status of the given Workbench"""

    def get(self, workbench_no: int) -> tp.Union[Response, dict[str, tp.Any]]:
        # find the WorkBench with the provided number
        try:
            workbench = self._get_workbench(workbench_no)
        except ValueError:
            return Response(status=404)

        workbench_status_dict: tp.Dict[str, tp.Any] = {
            "workbench_no": workbench.number,
            "state": workbench.state_number,
            "state_description": workbench.state_description,
            "employee_logged_in": workbench.employee.is_logged_in,
            "employee": workbench.employee.data,
            "operation_ongoing": workbench.is_operation_ongoing,
            "unit_internal_id": workbench.unit_in_operation
        }

        return workbench_status_dict

    @staticmethod
    def _get_workbench(workbench_no: int) -> WorkBench:
        global hub

        if not isinstance(workbench_no, int):
            raise ValueError

        workbench = hub.get_workbench_by_number(workbench_no)
        if workbench is None:
            raise ValueError

        return workbench


# REST API endpoints
api.add_resource(UnitCreationHandler, "/api/unit/new")
api.add_resource(UnitStartRecordHandler, "/api/unit/<unit_internal_id>/start")
api.add_resource(UnitEndRecordHandler, "/api/unit/<unit_internal_id>/end")
api.add_resource(UnitUploadHandler, "/api/unit/<unit_internal_id>/upload")
api.add_resource(EmployeeLogInHandler, "/api/employee/log-in")
api.add_resource(EmployeeLogOutHandler, "/api/employee/logout")
api.add_resource(WorkBenchStatusHandler, "/api/workbench/<int:workbench_no>")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
