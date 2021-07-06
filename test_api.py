import time

import requests

test_server = "http://127.0.0.1:5000"


def get_unit(test_server):
    resp = requests.post(test_server + "/api/unit/new", json={"workbench_no": 1})
    return resp


def test_employee_login():
    """Test to check if employee could be logged in system"""
    resp = requests.post(
        test_server + "/api/employee/log-in",
        json={"workbench_no": 1, "employee_rfid_card_no": "0008368511"},
    )

    assert resp.ok, f"{resp.json()}"
    assert resp.json()["status"] is True, f"{resp.json()}"

    employee_data = resp.json()["employee_data"]
    assert employee_data["name"] is not None
    assert employee_data["position"] is not None


unit = get_unit(test_server)


# def test_multiple_unit_creation():
#     """Test to check if multiple units could be created"""
#     for _ in range(3):
#         resp = requests.post(test_server + "/api/unit/new", json={"workbench_no": 1})
#         assert resp.json()["status"] is True
#
#         assert int(resp.json()["unit_internal_id"])


def test_unit_creation():
    """Test to check if one unit could be created"""
    assert unit.json()["status"] is True, f"{unit.json()}"


def test_unit_record_logged_in_employee():
    """Test to check if recording could be started when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = requests.post(
        test_server + f"/api/unit/{unit_id}/start",
        json={"workbench_no": 1, "production_stage_name": "packing", "additional_info": {}},
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True


def test_unit_stop_record_logged_employee():
    """Test to check if recording could be stopped when employee is logged in"""
    time.sleep(5)
    unit_id = unit.json()["unit_internal_id"]
    resp = requests.post(
        test_server + f"/api/unit/{unit_id}/end",
        json={"workbench_no": 1, "additional_info": {"test": "test"}},
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True


def test_unit_upload_logged_employee():
    """Test to check if recording could be uploaded when employee is logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = requests.post(
        test_server + f"/api/unit/{unit_id}/upload",
        json={"workbench_no": 1},
    )

    assert resp.status_code == 200, f"{resp.json()}"
    assert resp.json()["status"] is True, f"{resp.json()}"


def test_employee_logout():
    """Test to check if employee could be logged out"""
    logout_resp = requests.post(test_server + "/api/employee/log-out", json={"workbench_no": 1})

    assert logout_resp.ok, f"{logout_resp.json()}"
    assert logout_resp.json()["status"] is True, f"{logout_resp.json()}"


def test_unit_record_not_logged_in_employee():
    """Test to check if recording couldn't be started when employee not logged in"""
    unit_id = unit.json()["unit_internal_id"]
    resp = requests.post(
        test_server + f"/api/unit/{unit_id}/start",
        json={"workbench_no": 1, "production_stage_name": "packing", "additional_info": {}},
    )

    assert resp.json()["status"] is False, f"{resp.json()}"


def test_fake_employee_login():
    """Test to check if fake employee couldn't be logged in system"""
    resp = requests.post(
        test_server + "/api/employee/log-in",
        json={"workbench_no": 2, "employee_rfid_card_no": "0000000000"},
    )

    assert resp.json()["status"] is False, f"{resp.json()}"

    assert resp.json()["employee_data"] is None, f"{resp.json()}"


def test_employee_fake_logout():
    """Test to check if unauthorized employee couldn't be logged out"""
    logout_resp = requests.post(test_server + "/api/employee/log-out", json={"workbench_no": 1})

    assert logout_resp.json()["status"] is False, f"{logout_resp.json()}"


def test_workbench_status_handler():
    """Test to check if unauthorized employee couldn't be logged out"""
    status_resp = requests.get(test_server + "/api/workbench/1/status")

    assert status_resp.ok, f"{status_resp.json()}"
    assert status_resp.json() is not None, f"{status_resp.json()}"
