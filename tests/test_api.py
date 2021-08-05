import time

import requests
from feecc_hub_src.app import api
from fastapi.testclient import TestClient

client = TestClient(api)

TEST_SERVER = "http://127.0.0.1:5000"


def get_unit(server_address: str) -> requests.Response:
    resp = client.post(server_address + "/api/unit/new", json={"unit_type": "cryptoanalyzer"})
    return resp


def test_employee_login() -> None:
    """Test to check if employee could be logged in system"""
    resp = client.post(
        TEST_SERVER + "/api/employee/log-in",
        json={"workbench_no": 1, "employee_rfid_card_no": "1111111111"},
    )

    assert resp.ok, f"{resp.json()}"
    assert resp.json()["status"] is True, f"{resp.json()}"

    employee_data = resp.json()["employee_data"]
    assert employee_data["name"] is not None
    assert employee_data["position"] is not None


unit = get_unit(TEST_SERVER)


def test_unit_creation() -> None:
    """Test to check if one unit could be created"""
    assert unit.json()["status"] is True, f"{unit.json()}"


def test_unit_record_logged_in_employee() -> None:
    """Test to check if recording could be started when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = client.post(
        TEST_SERVER + f"/api/unit/{unit_id}/start",
        json={
            "workbench_no": 1,
            "production_stage_name": "packing",
            "additional_info": {"additional": "info 1"},
        },
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True


def test_unit_stop_record_logged_employee() -> None:
    """Test to check if recording could be stopped when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = client.post(
        TEST_SERVER + f"/api/unit/{unit_id}/end",
        json={"workbench_no": 1, "additional_info": {"test": "test"}},
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True


def test_unit_record_second_stage() -> None:
    """Test to check if recording could be started when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = client.post(
        TEST_SERVER + f"/api/unit/{unit_id}/start",
        json={
            "workbench_no": 1,
            "production_stage_name": "second",
            "additional_info": {"additional": "info"},
        },
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True, f"{resp.json()}"


def test_unit_stop_record_second_stage() -> None:
    """Test to check if recording could be stopped when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = client.post(
        TEST_SERVER + f"/api/unit/{unit_id}/end",
        json={"workbench_no": 1, "additional_info": {"test": "test"}},
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True


def test_unit_upload_logged_employee() -> None:
    """Test to check if recording could be uploaded when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = client.post(
        TEST_SERVER + f"/api/unit/{unit_id}/upload",
        json={"workbench_no": 1},
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True, f"{resp.json()}"


def test_employee_logout() -> None:
    """Test to check if employee could be logged out"""
    logout_resp = client.post(TEST_SERVER + "/api/employee/log-out", json={"workbench_no": 1})

    assert logout_resp.ok, f"{logout_resp.json()}"
    assert logout_resp.json()["status"] is True, f"{logout_resp.json()}"


def test_unit_record_not_logged_in_employee() -> None:
    """Test to check if recording couldn't be started when employee not logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = client.post(
        TEST_SERVER + f"/api/unit/{unit_id}/start",
        json={
            "workbench_no": 1,
            "production_stage_name": "packing",
            "additional_info": {},
        },
    )

    assert resp.json()["status"] is False, f"{resp.json()}"


def test_fake_employee_login() -> None:
    """Test to check if fake employee couldn't be logged in system"""
    resp = client.post(
        TEST_SERVER + "/api/employee/log-in",
        json={"workbench_no": 2, "employee_rfid_card_no": "0000000000"},
    )

    assert resp.json()["status"] is False, f"{resp.json()}"

    assert resp.json()["employee_data"] is None, f"{resp.json()}"


def test_employee_fake_logout() -> None:
    """Test to check if unauthorized employee couldn't be logged out"""
    logout_resp = client.post(TEST_SERVER + "/api/employee/log-out", json={"workbench_no": 1})

    assert logout_resp.json()["status"] is False, f"{logout_resp.json()}"


def test_workbench_status_handler() -> None:
    """Test to check if unauthorized employee couldn't be logged out"""
    status_resp = client.get(TEST_SERVER + "/api/workbench/1/status")

    assert status_resp.ok, f"{status_resp.json()}"
    assert status_resp.json() is not None, f"{status_resp.json()}"


def test_api_integrate() -> None:
    def check_state(expected: str) -> None:
        current_state = client.get(TEST_SERVER + "/api/workbench/2/status").json()
        assert (
            current_state["state"] == expected
        ), f"Failed to assert state. expected {expected}, got {current_state['state']}. state: {current_state}"
        time.sleep(0.1)

    def check_multiple_states(st1: str, st2: str) -> None:
        try:
            check_state(st1)
        except AssertionError:
            check_state(st2)

    check_state("AwaitLogin")

    login_resp = client.post(
        TEST_SERVER + "/api/employee/log-in",
        json={"workbench_no": 2, "employee_rfid_card_no": "1111111111"},
    )

    assert login_resp.json()["status"], f"Got error while logging in: {login_resp.json()}"

    check_state("AuthorizedIdling")

    test_unit = get_unit(TEST_SERVER)

    assert test_unit.json()["status"], f"Got error while creating unit: {test_unit.json()}"

    test_unit_id = test_unit.json()["unit_internal_id"]

    unit_start_resp = client.post(
        TEST_SERVER + f"/api/unit/{test_unit_id}/start",
        json={
            "workbench_no": 2,
            "production_stage_name": "Testing API",
            "additional_info": {"API": "Testing"},
        },
    )

    check_multiple_states("ProductionStageStarting", "ProductionStageOngoing")

    assert unit_start_resp.json()[
        "status"
    ], f"Got error while starting operation: {unit_start_resp.json()}"

    unit_stop_resp = client.post(
        TEST_SERVER + f"/api/unit/{test_unit_id}/end",
        json={"workbench_no": 2, "additional_info": {"test": "test"}},
    )

    check_multiple_states("ProductionStageEnding", "AuthorizedIdling")

    assert unit_stop_resp.json()[
        "status"
    ], f"Got error while stopping operation: {unit_stop_resp.json()}"

    unit_upload_resp = client.post(
        TEST_SERVER + f"/api/unit/{test_unit_id}/upload",
        json={"workbench_no": 2},
    )

    assert unit_stop_resp.json()[
        "status"
    ], f"Got error while wrapping up session: {unit_upload_resp.json()}"

    logout_resp = client.post(TEST_SERVER + "/api/employee/log-out", json={"workbench_no": 2})

    check_state("AwaitLogin")

    assert logout_resp.json()["status"]
