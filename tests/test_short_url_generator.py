import httpx

from feecc_workbench._short_url_generator import generate_short_url, update_short_url

FIRST_URL = "https://example.org"
SECOND_URL = "https://github.com"
short_url = ""


def get_underlying_url(target_short_url: str) -> str:
    return str(httpx.get(target_short_url).url)


def test_create_short_url() -> None:
    global short_url
    short_url = generate_short_url(FIRST_URL)
    underlying_url = get_underlying_url(short_url)
    assert underlying_url == FIRST_URL, f"Underlying URL does not match target. {underlying_url=} {short_url=}"


def test_update_short_url() -> None:
    global short_url
    update_short_url(short_url, SECOND_URL)
    underlying_url = get_underlying_url(short_url)
    assert underlying_url == SECOND_URL, f"Underlying URL does not match target. {underlying_url=} {short_url=}"
