import requests
from loguru import logger

from .Types import Config


def generate_short_url(config: Config) -> str:
    """
    :param config: dictionary containing all the configurations
    :type config: dict
    :return keyword: shorturl keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
    :return link: full yourls url. E.g. url.today/6b

    create an url to redirecting service to encode it in the qr and print. Redirecting to some dummy link initially
    just to print the qr, later the redirect link is updated with a gateway link to the video
    """
    url = f"https://{config['yourls']['server']}/yourls-api.php"
    querystring = {
        "username": config["yourls"]["username"],
        "password": config["yourls"]["password"],
        "action": "shorturl",
        "format": "json",
        "url": config["ipfs"]["gateway_address"],
    }  # api call to the yourls server. More on yourls.org
    payload = ""  # payload. Server creates a short url and returns it as a response

    try:
        response = requests.get(url, data=payload, params=querystring)
        logger.debug(response.text)
        keyword: str = response.json()["url"]["keyword"]
        link = str(config["yourls"]["server"]) + "/" + keyword  # link of form url.today/6b
        logger.info("Generating short url")
        logger.debug(response.json())
        return link
    except Exception as e:
        logger.error(f"Failed to create URL, replaced by url.today/55. Error: {e}")
        return "url.today/55"
        # time to time creating url fails. To go on just set a dummy url and keyword


def update_short_url(keyword: str, ipfs_hash: str, config: Config) -> None:
    """
    :param keyword: short url keyword. More on yourls.org. E.g. url.today/6b. 6b is a keyword
    :type keyword: str
    :param ipfs_hash: IPFS hash of a recorded video
    :type ipfs_hash: str
    :param config: dictionary containing all the configurations
    :type config: dict

    Update redirecting service so that now the short url points to the  gateway to a video in external_io
    """
    url = f"https://{config['yourls']['server']}/yourls-api.php"
    querystring = {
        "username": config["yourls"]["username"],
        "password": config["yourls"]["password"],
        "action": "update",
        "format": "json",
        "url": str(config["external_io"]["gateway_address"]) + ipfs_hash,
        "shorturl": keyword,
    }
    payload = ""  # api call with no payload just to update the link. More on yourls.org. Call created with insomnia

    try:
        response = requests.get(url, data=payload, params=querystring)
        # no need to read the response. Just wait till the process finishes
        logger.debug(f"Trying to update short url link: {response.json()}")
    except Exception as e:
        logger.error("Failed to update URL: ", e)
