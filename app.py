import atexit
import json
import logging
import typing as tp

from flask import Flask, Response, request
from flask_restful import Api, Resource

from feecc_hub.Hub import Hub
from feecc_hub.Unit import Unit
from feecc_hub.WorkBench import WorkBench

# set up logging
logging.basicConfig(
    level=logging.DEBUG,
    filename="hub.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)

# global variables
hub = Hub()
app = Flask(__name__)
api = Api(app)


@atexit.register
def end_session() -> None:
    """a function to execute when daemon exits"""

    logging.info("Sigterm registered. Handling.")
    global hub
    hub.end_session()
    logging.info("Sigterm handling success")


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
            return Response(response=json.dumps(response), status=200)

        except Exception as E:
            logging.error(f"Exception occurred while creating new Unit:\n{E}")
            response = {
                "status": False,
                "comment": "Could not create a new Unit. Internal error occurred",
            }
            return Response(response=json.dumps(response), status=500)


class UnitStartRecordHandler(Resource):
    """handle start recording operation on a Unit"""

    @staticmethod
    def post(unit_internal_id: str) -> Response:
        global hub
        request_payload: tp.Dict[str, tp.Any] = request.get_json()

        try:
            workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
            unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)

            if unit is None:
                err_msg = f"No unit with internal id {unit_internal_id}"
                raise ValueError(err_msg)

            workbench.start_operation(unit, request_payload["production_stage_name"],
                                      request_payload["additional_info"])
            message = f"Started operation '{request_payload['production_stage_name']}' on Unit {unit_internal_id} at " \
                      f"Workbench no. {request_payload['workbench_no']} "
            response_data = {
                "status": True,
                "comment": message
            }
            logging.info(message)
            return Response(status=200, response=json.dumps(response_data))

        except Exception as E:
            message = f"Couldn't handle request. An error occurred: {E}"
            logging.error(message)
            logging.debug(request_payload)
            response_data = {
                "status": False,
                "comment": message
            }
            return Response(response=json.dumps(response_data), status=500)


class UnitEndRecordHandler(Resource):
    """handle end recording operation on a Unit"""

    @staticmethod
    def post(unit_internal_id: str) -> Response:
        global hub
        request_payload: tp.Dict[str, tp.Any] = request.get_json()

        logging.info(f"Received a request to end record for unit with int. id {unit_internal_id}")
        logging.debug(request_payload)

        try:
            workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
            workbench.end_operation(unit_internal_id)
            return Response(status=200, response=json.dumps({"status": True, "comment": "ok"}))
        except Exception as e:
            logging.error(f"Couldn't handle end record request. An error occurred: {e}")
            return Response(
                response=json.dumps({
                    "status": False,
                    "comment": "Couldn't handle end record request."
                }),
                status=500)


class UnitUploadHandler(Resource):
    """handle Unit lifecycle end"""

    @staticmethod
    def post(unit_internal_id: str) -> Response:
        global hub
        request_payload: tp.Dict[str, tp.Any] = request.get_json()

        logging.info(f"Received a request to upload unit with int. id {unit_internal_id}")
        logging.debug(request_payload)

        try:
            unit: Unit = hub.get_unit_by_internal_id(unit_internal_id)
            unit.upload()
            return Response(
                response=json.dumps({
                    "status": True,
                    "comment": f"uploaded data for unit {unit_internal_id}",
                }),
                status=200)
        except Exception as e:
            logging.error(f"Can't handle unit upload. An error occurred: {e}")

        return Response(
            response=json.dumps({'status': False, "comment": "Can't handle unit upload"}), status=500
        )


# Employee operations handling
class EmployeeLogInHandler(Resource):
    """handle logging in the Employee at a given Workbench"""

    @staticmethod
    def post() -> Response:
        global hub
        request_payload: tp.Dict[str, tp.Any] = request.get_json()

        logging.info("Handling logging in the employee")
        logging.debug(request_payload)

        try:
            workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
            workbench.start_shift(request_payload["employee_rfid_card_no"])

            if workbench.employee is not None:
                response_data = {
                    "status": True,
                    "comment": "Employee logged in successfully",
                    "employee_data": workbench.employee.data
                }

                return Response(response=json.dumps(response_data), status=200)

            else:
                raise ValueError

        except ValueError:
            message = "Could not log in the Employee. Authentication failed."
            logging.error(message)

            response_data = {
                "status": False,
                "comment": message
            }

            return Response(response=json.dumps(response_data), status=401)

        except Exception as e:
            message = f"An error occurred while logging in the Employee:\n{e}"
            logging.error(message)

            response_data = {
                "status": False,
                "comment": message
            }

            return Response(response=json.dumps(response_data), status=500)


class EmployeeLogOutHandler(Resource):
    """handle logging out the Employee at a given Workbench"""

    @staticmethod
    def post() -> Response:
        global hub
        request_payload: tp.Dict[str, tp.Any] = request.get_json()

        logging.info("Handling logging out the employee")
        logging.debug(request_payload)

        try:
            workbench: WorkBench = hub.get_workbench_by_number(request_payload["workbench_no"])
            workbench.end_shift()

            if workbench.employee is None:
                response_data = {
                    "status": True,
                    "comment": "Employee logged out successfully",
                }

                return Response(response=json.dumps(response_data), status=200)

            else:
                raise ValueError

        except Exception as e:
            message = f"An error occurred while logging out the Employee:\n{e}"
            logging.error(message)

            response_data = {
                "status": False,
                "comment": message
            }

            return Response(response=json.dumps(response_data), status=500)


# Employee operations handling
class WorkBenchStatusHandler(Resource):
    """handle providing status of the given Workbench"""

    def get(self, workbench_no: int) -> Response:
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

        return Response(response=json.dumps(workbench_status_dict), status=200)

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
    # start the server
    host: str = hub.config["api_server"]["ip"]
    port: int = hub.config["api_server"]["port"]
    app.run(host=host, port=port)
