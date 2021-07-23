import unittest

from feecc_hub_src.feecc_hub.database import MongoDbWrapper
from mockupdb import *
import os
import requests

test_login, test_password = os.environ.get("secrets.MONGO_LOGIN"), os.environ.get(
    "secrets.MONGO_PASS"
)


def test_check_credentials():
    assert test_login is not None
    assert test_password is not None


test_db_url = f"mongodb+srv://{test_login}:{test_password}@netmvas.hx3jm.mongodb.net/Feecc-Hub?retryWrites=true&w=majority&ssl=true&ssl_cert_reqs=CERT_NONE"

wrapper = MongoDbWrapper(test_login, test_password)


def test_connection():
    resp = wrapper.mongo_client.admin.command("ismaster")
    assert resp is not None, "Connection failed"


def test_abstract_schemas():
    cnt_employee = wrapper.mongo_client["Feecc-Hub"]["Employee-data"].count_documents({})
    assert cnt_employee > 0, "No employees or collection 'Employee-data' found"

    # cnt_stages = wrapper.mongo_client["Feecc-Hub"]["Production-stages-data"].count_documents({})
    # assert cnt_stages > -1, "No prod. stages or collection 'Production-stages-data' found"

    cnt_units = wrapper.mongo_client["Feecc-Hub"]["Unit-data"].count_documents({})
    assert cnt_units > 0, "No units or collection 'Unit-data' found"


def test_upload_dict():
    pass


def test_upload_dataclass():
    pass


def test_find_item():
    pass


def test_find_many():
    pass


def test_get_all_items_in_collection():
    pass
