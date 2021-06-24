import dataclasses
import os
import tempfile
from pprint import pprint

import pytest
import requests
import responses

from app import hub


@pytest.fixture
def test_server():
    return "http://127.0.0.1:5000"


def test_api_working(test_server):
    """Can't connect to server means server down"""
    r = requests.get(test_server)
    assert r.ok is False


@responses.activate
def test_unit_creation_handler_responding(test_server):
    """test unit creation handler"""
    responses.add(responses.POST, test_server + "/api/unit/new", json={"status": True}, status=200)
    resp = requests.post(test_server + "/api/unit/new", json={"workbench_no": 0})

    assert resp.json() == {"status": True}

    assert len(responses.calls) == 1
