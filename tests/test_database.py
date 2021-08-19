import os

from feecc_hub_src.feecc_hub.Config import Config
from feecc_hub_src.feecc_hub.database import MongoDbWrapper


def credentials():
    try:
        return os.environ["MONGO_LOGIN"], os.environ["MONGO_PASS"]
    except KeyError:
        db_cfg = Config().global_config["mongo_db"]
        return db_cfg["username"], db_cfg["password"]


test_login, test_password = credentials()


def test_check_credentials() -> None:
    assert test_login is not None
    assert test_password is not None


wrapper = MongoDbWrapper(test_login, test_password)


def test_connection() -> None:
    resp = wrapper.mongo_client.admin.command("ismaster")
    assert resp is not None, "Connection failed"


def test_abstract_schemas() -> None:
    cnt_employee = wrapper.mongo_client["Feecc-Hub"]["Employee-data"].count_documents({})
    assert cnt_employee > 0, "No employees or collection 'Employee-data' found"

    # cnt_stages = wrapper.mongo_client["Feecc-Hub"]["Production-stages-data"].count_documents({})
    # assert cnt_stages > -1, "No prod. stages or collection 'Production-stages-data' found"

    cnt_units = wrapper.mongo_client["Feecc-Hub"]["Unit-data"].count_documents({})
    assert cnt_units > 0, "No units or collection 'Unit-data' found"


def test_upload_dict() -> None:
    pass


def test_upload_dataclass() -> None:
    pass


def test_find_item() -> None:
    pass


def test_find_many() -> None:
    pass


def test_get_all_items_in_collection() -> None:
    pass
