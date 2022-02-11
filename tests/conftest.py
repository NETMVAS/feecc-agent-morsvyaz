import pytest


def pytest_addoption(parser):
    parser.addoption("--short-url", action="store_true", default=False, help="run short url generator tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--short-url"):
        return

    skip_short_url = pytest.mark.skip(reason="need --short-url option to run")

    for item in items:
        if "short_url" in item.keywords:
            item.add_marker(skip_short_url)
