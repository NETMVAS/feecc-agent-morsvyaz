import pytest
import requests


@pytest.fixture
def test_server():
    return "http://127.0.0.1:5000"


def test_api_working(test_server):
    """Can't connect to server means server down"""
    r = requests.get(test_server)
    assert r.ok is False


def test_unit_creation(test_server):
    """Test to check if one unit could be created"""
    resp = requests.post(test_server + "/api/unit/new", json={"workbench_no": 1})

    assert resp.json()["status"] is True


def test_multiple_unit_creation(test_server):
    """Test to check if multiple units could be created"""
    for i in range(1, 4):
        resp = requests.post(test_server + "/api/unit/new", json={"workbench_no": i})
        assert resp.json()["status"] is True

        assert int(resp.json()["unit_internal_id"])


def test_unit_record_unlogged_employee(test_server):
    """Test to check if recording couldn't be started when employee unlogged"""
    resp = requests.post(test_server + "/api/unit/1/start",
                         json={"workbench_no": 1, "production_stage_name": "packing", "additional_info": {}})

    # FIXME: когда сотрудник не залогинен, система падает :)

    assert resp.status_code == 500
    assert resp.json()["status"] is False


def test_employee_login(test_server):
    """Test to check if employee could be logged in system"""
    resp = requests.post(test_server + "/api/employee/log-in",
                         json={"workbench_no": 1, "employee_rfid_card_no": "0008368511"})

    assert resp.ok
    assert resp.json()["status"] is True

    employee_data = resp.json()["employee_data"]
    assert employee_data["name"] is not None
    assert employee_data["position"] is not None


def test_employee_logout(test_server):
    """Test to check if employee could be logged out"""
    login_resp = requests.post(test_server + "/api/employee/log-in",
                         json={"workbench_no": 1, "employee_rfid_card_no": "0008368511"})

    assert login_resp.ok

    logout_resp = requests.post(test_server + "/api/employee/log-out",
                         json={"workbench_no": 1})

    # FIXME: почему-то возвращается 404, допилить логгинг, ибо непонятно. Сотрудник какбе есть, а разлогиниться не получается
    assert logout_resp.ok
    assert logout_resp.json()["status"] is True
