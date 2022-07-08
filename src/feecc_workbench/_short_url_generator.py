import httpx
from loguru import logger

from .config import CONFIG
from .Messenger import messenger
from .utils import async_time_execution, service_is_up

YOURLS_CONFIG = CONFIG.yourls


@async_time_execution
async def generate_short_url(underlying_url: str | None = None) -> str:
    """
    :return keyword: shorturl keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
    :return link: full yourls url. E.g. url.today/6b

    create an url to redirecting service to encode it in the qr and print. Redirecting to some dummy link initially
    just to print the qr, later the redirect link is updated with a gateway link to the video
    """
    logger.debug("Generating dummy short url to replace with actual link later")
    url = f"https://{YOURLS_CONFIG.server}/yourls-api.php"
    querystring = {
        "username": YOURLS_CONFIG.username,
        "password": YOURLS_CONFIG.password,
        "action": "shorturl",
        "format": "json",
        "url": underlying_url or "example.com",
    }  # api call to the yourls server. More on yourls.org

    if not service_is_up(url):
        message = f"Yourls server {url} is unreachable"
        messenger.error(message)
        raise ConnectionError(message)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=querystring)

    if response.is_error:
        messenger.error(f"Yourls returned an error: {response.text}")
        raise httpx.RequestError(response.text)

    logger.debug(f"{YOURLS_CONFIG.server} returned: {response.text}")
    keyword: str = response.json()["url"]["keyword"]
    link = f"https://{str(YOURLS_CONFIG.server)}/{keyword}"
    logger.info(f"Assigned yourls link: {link}")
    return link


@async_time_execution
async def update_short_url(short_url: str, new_url: str) -> None:
    """Update redirecting service so that now the short url points to the  gateway to a video in external_io"""
    keyword = short_url.split("/")[-1]
    url = f"https://{YOURLS_CONFIG.server}/yourls-api.php"
    params = {
        "username": YOURLS_CONFIG.username,
        "password": YOURLS_CONFIG.password,
        "action": "update",
        "format": "json",
        "url": new_url,
        "shorturl": keyword,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)

    logger.debug(f"Trying to update short url link. Keyword: {keyword}")

    if response.status_code != 200:
        logger.warning("Failed to update short url link")
