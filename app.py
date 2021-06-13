import json

from flask import Flask, request, Response
from flask_restful import Api, Resource
import typing as tp
import logging
import yaml
from sys import exit

import State
from Agent import Agent
from Passport import Passport
from Employee import Employee
from modules.Camera import Camera

# set up logging
logging.basicConfig(
    level=logging.INFO,
    filename="agent.log",
    format="%(asctime)s %(levelname)s: %(message)s"
)

logging.info('Agent API listener started')

# global variables
valid_states = [0, 1, 2, 3]
config: tp.Dict[str, tp.Dict[str, tp.Any]] = read_configuration()
backend_api_address: str = config["api_address"]["backend_api_address"]

# instantiate objects
agent = Agent(config=config, camera_config=config["camera"])
agent.backend_api_address = backend_api_address
passport = Passport("0008368511", config)
logging.debug(f"Created dummy passport: {passport}")
app = Flask(__name__)
api = Api(app)


# REST API request handlers
class FormHandler(Resource):
    """accepts a filled form from the backend and uses it to form a unit passport"""

    @staticmethod
    def post() -> int:
        logging.info(
            f"Received a form. Parsing and validating"
        )

        # parse the form data
        form_data = request.get_json()

        global agent
        global passport

        # validate the form and change own state
        if passport.submit_form(form_data):
            agent.associated_passport = passport
            agent.execute_state(State.State2)

            logging.info(
                f"Form validation success. Current state: {agent.state}"
            )

        else:
            agent.execute_state(State.State0)

            logging.error(
                f"""
                Invalid form, state reset to 0
                Form: {form_data}
                Current state: {agent.state}
                """
            )

        return 200


class StateUpdateHandler(Resource):
    """handles a state update request"""

    @staticmethod
    def post():
        logging.info(
            f"Received a request to update the state."
        )

        # parse the request data
        data = request.get_json()

        # validate the request
        global valid_states
        global agent

        if not data["change_state_to"] in valid_states:
            logging.warning(
                f"Invalid state transition: '{data['change_state_to']}' is not a valid state. Staying at {agent.state}"
            )

            return Response(
                response={"status": 406, "msg": "invalid state"},
                status=406
            )

        # change own state to the one specified by the sender
        # garbage temporary solution
        states = [State.State0, State.State1, State.State2, State.State3]
        new_state = states[data["change_state_to"]]
        agent.execute_state(new_state)

        logging.info(
            f"Successful state transition to {data['change_state_to']}"
        )

        return Response(status=200)


class RFIDHandler(Resource):
    """handles RFID scanner events"""

    @staticmethod
    def post() -> str:

        # parse RFID card ID from the request
        card_id = request.get_json()["string"]

        # log the event
        logging.info(f"read RFID card with ID {card_id}")

        employee_data = Employee.find_in_db(card_id)

        # check if employee in the database
        if employee_data is None:
            return Response(
                {
                    "is_valid": False,
                    "employee_name": "",
                    "position": "",
                    "comment": "Employee not found"
                },
                status=404
            )

        # start session
        if agent.state == 0:

            # create a passport for the provided employee
            try:
                global passport
                passport = Passport(card_id, config)
                logging.debug(f"Created passport for {card_id}: {passport}")
                agent.execute_state(State.State1)

            except ValueError:
                logging.info(f"Passport creation failed, staying at state 0")

        # cancel session
        elif agent.state == 1:
            agent.execute_state(State.State0)

        # end session
        elif agent.state == 2:
            agent.execute_state(State.State3)

        # ignore interaction when in state 3
        else:
            pass

        return Response(
            {
                "is_valid": True,
                "employee_name": employee_data[0],
                "position": employee_data[1],
                "comment": ""
            },
            status=200
        )


class PassportAppendHandler(Resource):
    """
    Handles requests for additional recordings to unit passport

    POST must contain JSON like:
    {"barcode_string": "", "employee_name": "", "position": ""}

    Response looks like:
    {"status": true/false, "comment": "..."}
    """

    @staticmethod
    def validate_form(json_data: tp.Dict[str, str]) -> tp.Tuple[bool, str]:
        """
        Method used to validate additional recordings to unit passport form

        Args:
            json_data (str): JSON query.

        Examples:
            >>> x = {"barcode_string": "123", "employee_name": "Nikolas", "position": "Engineer"}
            >>> PassportAppendHandler.validate_form(x)

        Returns:
            True if validation succeed, False if not
        """
        expected_keys = ["barcode_string", "employee_name", "position", "spoke_num"]

        try:
            actual_keys = list(json_data.keys())
        except json.decoder.JSONDecodeError as E:
            logging.error(f"Failed to parse JSON. {E}")
            return False, "Unknown format (expected JSON)"

        if expected_keys != actual_keys:
            return False, "Form have extra/missing fields"

        for key, entry in json_data.items():
            if not entry:
                logging.error(f"Passport form contains empty field: {entry}")
                return False, "Form contains empty field"

        matching_uuid = passport.match_passport_id_with_hash(passport_id=json_data["barcode_string"])

        if matching_uuid is None:
            return False, "Matching passport not found"

        return True, ""

    def post(self) -> str:
        data = request.get_json()

        is_valid, comment = self.validate_form(data)

        matching_camera = Camera.match_camera_with_table(data["spoke_num"])

        if is_valid and matching_camera is not None:
            agent.associated_passport = passport
            agent.execute_state(State.State2)

            logging.info(
                f"Form validation success. Current state: {agent.state}, camera data: {matching_camera}"
            )

            return Response(
                {
                    "status": True,
                    "comment": comment
                },
                status=200
            )

        agent.execute_state(State.State0)

        logging.error(
            f"""
            Invalid form, state reset to 0
            Form: {data}
            Current state: {agent.state}
            """
        )

        return Response(
            {
                "status": False,
                "comment": comment
            },
            status=400
        )


# REST API endpoints
api.add_resource(FormHandler, "/api/form-handler")
api.add_resource(StateUpdateHandler, "/api/state-update")
api.add_resource(RFIDHandler, "/api/rfid")
api.add_resource(PassportAppendHandler, "/api/passport")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
