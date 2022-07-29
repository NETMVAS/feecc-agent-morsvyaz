import os
from copy import copy
from time import sleep
from typing import no_type_check

from fastapi.testclient import TestClient
from requests import Response

from app import app
from feecc_workbench.states import State

CLIENT = TestClient(base_url="http://127.0.0.1:5000", app=app)
VALID_TEST_CARD = "1111111111"
VALID_SIMPLE_SCHEMA_ID = "test_simple_unit_1"
VALID_COMPOSITE_SCHEMA_ID = "test_composite_unit_1"
VALID_HID_RFID_DEVICE_NAME = "IC Reader IC Reader"
VALID_HID_BARCODE_DEVICE_NAME = "Newtologic  NT1640S"
SLOW_MODE = bool(os.environ.get("SLOW_MODE", None))
SLOW_MODE_DELAY = int(os.environ.get("SLOW_MODE_DELAY", 3))


def wait() -> None:
    """wait some time to see the frontend response to the backend state switching"""
    if SLOW_MODE:
        sleep(SLOW_MODE_DELAY)


def check_status(response: Response, target_status: int = 200) -> None:
    assert response.status_code in [200, target_status], f"Request status code was {response.status_code}"
    if response.status_code == 200:
        assert response.json()["status_code"] == target_status


def check_state(target_state: State) -> None:
    response = CLIENT.get("/workbench/status")
    assert response.status_code == 200, f"Request status code was {response.status_code}"
    assert (
        response.json()["state"] == target_state.value
    ), f"Expected state {target_state.value}, got {response.json()['state']}"


def login(card: str) -> None:
    CLIENT.post("/employee/log-in", json={"employee_rfid_card_no": card})


def test_server_is_up() -> None:
    response = CLIENT.get("/")
    check_status(response, 404)


def test_valid_get_info() -> None:
    response = CLIENT.post("/employee/info", json={"employee_rfid_card_no": VALID_TEST_CARD})
    check_status(response, 200)


def test_invalid_get_info() -> None:
    response = CLIENT.post("/employee/info", json={"employee_rfid_card_no": "string"})
    check_status(response, 404)


def test_invalid_login() -> None:
    check_state(target_state=State.AWAIT_LOGIN_STATE)
    login("42")
    check_state(target_state=State.AWAIT_LOGIN_STATE)


def test_invalid_logout() -> None:
    check_state(target_state=State.AWAIT_LOGIN_STATE)
    response = CLIENT.post("/employee/log-out")
    check_status(response, 500)


def test_valid_login() -> None:
    check_state(target_state=State.AWAIT_LOGIN_STATE)
    login(VALID_TEST_CARD)
    check_state(target_state=State.AUTHORIZED_IDLING_STATE)
    wait()


def test_valid_logout() -> None:
    check_state(target_state=State.AUTHORIZED_IDLING_STATE)
    CLIENT.post("/employee/log-out")
    check_state(target_state=State.AWAIT_LOGIN_STATE)
    wait()


simple_unit_internal_id: str = ""
composite_unit_internal_id: str = ""


def test_get_unit_data_invalid() -> None:
    response = CLIENT.get("/unit/42/info")
    check_status(response, 404)


def test_create_new_simple_unit_unauthorized() -> None:
    response = CLIENT.post(f"/unit/new/{VALID_SIMPLE_SCHEMA_ID}")
    check_status(response, 500)


def test_create_new_simple_unit() -> None:
    login(VALID_TEST_CARD)
    response = CLIENT.post(f"/unit/new/{VALID_SIMPLE_SCHEMA_ID}")
    check_status(response, 200)
    global simple_unit_internal_id
    assert "unit_internal_id" in response.json()
    simple_unit_internal_id = response.json().get("unit_internal_id")


def test_get_simple_unit_data_valid() -> None:
    global simple_unit_internal_id
    response = CLIENT.get(f"/unit/{simple_unit_internal_id}/info")
    check_status(response, 200)
    data = response.json()
    assert data.get("unit_internal_id") == simple_unit_internal_id, "Internal ID mismatch"
    assert data.get("unit_biography_completed") == [], "Unexpected biography entries"
    assert data.get("unit_components") is None, "Components found in a simple unit"


def test_create_new_composite_unit() -> None:
    response = CLIENT.post(f"/unit/new/{VALID_COMPOSITE_SCHEMA_ID}")
    check_status(response, 200)
    global composite_unit_internal_id
    assert "unit_internal_id" in response.json()
    composite_unit_internal_id = response.json().get("unit_internal_id")


def test_get_composite_unit_data_valid() -> None:
    global composite_unit_internal_id
    response = CLIENT.get(f"/unit/{composite_unit_internal_id}/info")
    check_status(response, 200)
    data = response.json()
    assert data.get("unit_internal_id") == composite_unit_internal_id, "Internal ID mismatch"
    assert data.get("unit_biography_completed") == [], "Unexpected biography entries"
    assert data.get("unit_components") == [
        VALID_SIMPLE_SCHEMA_ID
    ], f"Components not found for {composite_unit_internal_id}"


def test_get_workbench_status() -> None:
    response = CLIENT.get("/workbench/status")
    assert response.status_code == 200, "Status request failed"


def test_assign_simple_unit() -> None:
    global simple_unit_internal_id
    response = CLIENT.post(f"/workbench/assign-unit/{simple_unit_internal_id}")
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    wait()


def test_start_operation_simple_unit() -> None:
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    response = CLIENT.post(
        "/workbench/start-operation",
        json={
            "additional_info": {"additionalProp1": "string", "additionalProp2": "string", "additionalProp3": "string"},
        },
    )
    check_status(response, 200)
    check_state(State.PRODUCTION_STAGE_ONGOING_STATE)
    wait()


def test_end_operation_simple_unit() -> None:
    check_state(State.PRODUCTION_STAGE_ONGOING_STATE)
    response = CLIENT.post(
        "/workbench/end-operation",
        json={
            "additional_info": {"additionalProp1": "string", "additionalProp2": "string", "additionalProp3": "string"}
        },
    )
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    wait()


def test_remove_unit() -> None:
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    response = CLIENT.post("/workbench/remove-unit")
    check_status(response, 200)
    check_state(State.AUTHORIZED_IDLING_STATE)
    wait()


def test_assign_composite_unit() -> None:
    global composite_unit_internal_id
    response = CLIENT.post(f"/workbench/assign-unit/{composite_unit_internal_id}")
    check_status(response, 200)
    check_state(State.GATHER_COMPONENTS_STATE)
    wait()


def test_remove_unit_while_gathering() -> None:
    check_state(State.GATHER_COMPONENTS_STATE)
    response = CLIENT.post("/workbench/remove-unit")
    check_status(response, 200)
    check_state(State.AUTHORIZED_IDLING_STATE)
    wait()


def test_assign_invalid_component() -> None:
    test_assign_composite_unit()
    check_state(State.GATHER_COMPONENTS_STATE)
    response = CLIENT.post("/unit/assign-component/3050673369727")
    check_status(response, 404)
    check_state(State.GATHER_COMPONENTS_STATE)


def test_assign_valid_component() -> None:
    check_state(State.GATHER_COMPONENTS_STATE)
    global simple_unit_internal_id
    response = CLIENT.post(f"/unit/assign-component/{simple_unit_internal_id}")
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    wait()


def test_start_operation_composite_unit() -> None:
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    response = CLIENT.post(
        "/workbench/start-operation",
        json={
            "additional_info": {"additionalProp1": "string", "additionalProp2": "string", "additionalProp3": "string"},
        },
    )
    check_status(response, 200)
    check_state(State.PRODUCTION_STAGE_ONGOING_STATE)
    wait()


def test_end_operation_prematurely() -> None:
    check_state(State.PRODUCTION_STAGE_ONGOING_STATE)
    response = CLIENT.post(
        "/workbench/end-operation",
        json={
            "premature_ending": True,
            "additional_info": {"additionalProp1": "string", "additionalProp2": "string", "additionalProp3": "string"},
        },
    )
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    wait()


def test_start_operation_again() -> None:
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    response = CLIENT.post(
        "/workbench/start-operation",
        json={
            "additional_info": {"additionalProp1": "string", "additionalProp2": "string", "additionalProp3": "string"},
        },
    )
    check_status(response, 200)
    check_state(State.PRODUCTION_STAGE_ONGOING_STATE)
    wait()


def test_end_operation_composite_unit() -> None:
    check_state(State.PRODUCTION_STAGE_ONGOING_STATE)
    response = CLIENT.post(
        "/workbench/end-operation",
        json={
            "additional_info": {"additionalProp1": "string", "additionalProp2": "string", "additionalProp3": "string"}
        },
    )
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    wait()


def test_biography_stage_count_correct() -> None:
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    response = CLIENT.get("/workbench/status")
    assert len(response.json().get("unit_biography", [])) == 2, "Expected 2 stages in unit biography"


def test_upload_unit() -> None:  # FIXME: False positive when GW is offline
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    response = CLIENT.post("/unit/upload")
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)


def test_get_schemas_list() -> None:
    response = CLIENT.get("/workbench/production-schemas/names")
    check_status(response, 200)
    assert response.json().get("available_schemas", None), "No schema names were returned"


def test_get_schema_by_id_invalid() -> None:
    response = CLIENT.get("/workbench/production-schemas/42")
    check_status(response, 404)


def test_get_schema_by_id_valid() -> None:
    response = CLIENT.get(f"/workbench/production-schemas/{VALID_SIMPLE_SCHEMA_ID}")
    check_status(response, 200)


@no_type_check
def send_hid_event(string: str, sender: str) -> Response:
    payload = {"string": string, "name": sender}
    return CLIENT.post("/workbench/hid-event", json=payload)


def test_hid_event_unknown_sender() -> None:
    response = send_hid_event("123", "sender")
    check_status(response, 404)


def test_hid_event_known_sender() -> None:
    response = send_hid_event("123", VALID_HID_RFID_DEVICE_NAME)
    check_status(response, 200)


def test_hid_event_login() -> None:
    check_state(target_state=State.AWAIT_LOGIN_STATE)
    send_hid_event(VALID_TEST_CARD, VALID_HID_RFID_DEVICE_NAME)
    check_state(target_state=State.AUTHORIZED_IDLING_STATE)
    wait()


old_simple_unit_int_id = ""


def prepare_new_units() -> None:
    test_create_new_composite_unit()
    global old_simple_unit_int_id
    old_simple_unit_int_id = copy(simple_unit_internal_id)
    test_create_new_simple_unit()
    test_assign_simple_unit()
    test_start_operation_simple_unit()
    test_end_operation_simple_unit()


def test_hid_event_assign_unit() -> None:
    prepare_new_units()
    global composite_unit_internal_id
    response = send_hid_event(composite_unit_internal_id, VALID_HID_BARCODE_DEVICE_NAME)
    check_status(response, 200)
    check_state(State.GATHER_COMPONENTS_STATE)
    wait()


def test_hid_event_assign_component_already_featured_in_another_composite() -> None:
    check_state(State.GATHER_COMPONENTS_STATE)
    global old_simple_unit_int_id
    response = send_hid_event(old_simple_unit_int_id, VALID_HID_BARCODE_DEVICE_NAME)
    check_status(response, 500)
    check_state(State.GATHER_COMPONENTS_STATE)
    wait()


def test_hid_event_assign_component() -> None:
    check_state(State.GATHER_COMPONENTS_STATE)
    global simple_unit_internal_id
    response = send_hid_event(simple_unit_internal_id, VALID_HID_BARCODE_DEVICE_NAME)
    check_status(response, 200)
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    wait()


def test_hid_event_assign_another_unit() -> None:
    check_state(State.UNIT_ASSIGNED_IDLING_STATE)
    global simple_unit_internal_id
    response = send_hid_event(simple_unit_internal_id, VALID_HID_BARCODE_DEVICE_NAME)
    check_status(response, 500)
    check_state(State.AUTHORIZED_IDLING_STATE)
    wait()


def test_hid_event_logout() -> None:
    check_state(target_state=State.AUTHORIZED_IDLING_STATE)
    send_hid_event(VALID_TEST_CARD, VALID_HID_RFID_DEVICE_NAME)
    check_state(target_state=State.AWAIT_LOGIN_STATE)
    wait()
