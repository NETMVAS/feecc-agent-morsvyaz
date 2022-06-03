from typing import no_type_check

import pytest


@no_type_check
def pytest_addoption(parser) -> None:
    parser.addoption("--short-url", action="store_true", default=False, help="run short url generator tests")


@no_type_check
def pytest_collection_modifyitems(config, items) -> None:
    if config.getoption("--short-url"):
        return

    skip_short_url = pytest.mark.skip(reason="need --short-url option to run")

    for item in items:
        if "short_url" in item.keywords:
            item.add_marker(skip_short_url)
