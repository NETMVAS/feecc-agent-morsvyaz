import requests
from loguru import logger

from .config import config


def generate_short_url() -> str:
    """
    :return keyword: shorturl keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
    :return link: full yourls url. E.g. url.today/6b

    create an url to redirecting service to encode it in the qr and print. Redirecting to some dummy link initially
    just to print the qr, later the redirect link is updated with a gateway link to the video
    """
    logger.debug("Generating dummy short url to replace with actual link later")

    config_ = config.yourls
    url = f"https://{config_.server}/yourls-api.php"
    querystring = {
        "username": config_.username,
        "password": config_.password,
        "action": "shorturl",
        "format": "json",
        "url": "example.com",
    }  # api call to the yourls server. More on yourls.org
    payload = ""  # payload. Server creates a short url and returns it as a response

    try:
        response = requests.get(url, data=payload, params=querystring)
        logger.debug(f"{config_.server} returned: {response.text}")
        keyword: str = response.json()["url"]["keyword"]
        link = str(config_.server) + "/" + keyword  # link of form url.today/6b
        logger.info(f"Assigned yourls link: {link}")
        return link
    except Exception as E:
        logger.error(f"Failed to create URL, replaced by fake link (url.today/55). Error: {E}")
        return "url.today/55"


def update_short_url(keyword: str, ipfs_hash: str) -> None:
    """
    :param keyword: short url keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
    :type keyword: str
    :param ipfs_hash: IPFS hash of a recorded video
    :type ipfs_hash: str

    Update redirecting service so that now the short url points to the  gateway to a video in external_io
    """
    url = f"https://{config.ipfs}/yourls-api.php"
    new_file_url: str = f"{config.ipfs}{ipfs_hash}"
    params = {
        "username": config.yourls.username,
        "password": config.yourls.password,
        "action": "update",
        "format": "json",
        "url": new_file_url,
        "shorturl": keyword,
    }
    payload = ""  # api call with no payload just to update the link. More on yourls.org. Call created with insomnia

    try:
        response = requests.get(url, data=payload, params=params)
        logger.debug(f"Trying to update short url link. Keyword: {keyword}")

        if response.status_code != 200:
            logger.warning("Failed to update short url link")
    except Exception as E:
        logger.error(f"Failed to update URL: {E}")
