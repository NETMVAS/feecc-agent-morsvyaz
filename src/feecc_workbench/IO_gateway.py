import socket
import typing as tp

import httpx
from loguru import logger
from robonomicsinterface import RobonomicsInterface

from ._image_generation import create_qr
from ._short_url_generator import generate_short_url
from .config import config
from .utils import get_headers, time_execution

IO_GATEWAY_ADDRESS: str = config.workbench_config.feecc_io_gateway_socket
ROBONOMICS_CLIENT = RobonomicsInterface(
    seed=config.robonomics_network.account_seed, remote_ws=config.robonomics_network.substrate_node_url
)


def gateway_is_up() -> None:
    """check if camera is reachable on the specified port and ip"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)

    try:
        gw_socket_no_proto = IO_GATEWAY_ADDRESS.split("//")[1]
        ip, port = gw_socket_no_proto.split(":")
        s.connect((ip, int(port)))
        logger.debug(f"{IO_GATEWAY_ADDRESS} is up")
        s.close()

    except socket.error:
        raise BrokenPipeError(f"{IO_GATEWAY_ADDRESS} is unreachable")

    except Exception as e:
        logger.error(e)


@time_execution
def generate_qr_code() -> tp.Tuple[str, str]:
    """generate a QR code with the short link"""
    short_url: str = generate_short_url()
    qrcode_path: str = create_qr(short_url)
    return short_url, qrcode_path


@time_execution
def post_to_datalog(content: str) -> None:
    """echo provided string to the Robonomics datalog"""
    logger.info(f"Posting data '{content}' to Robonomics datalog")
    txn_hash: str = ROBONOMICS_CLIENT.record_datalog(content)
    logger.info(f"Data '{content}' has been posted to the Robonomics datalog. {txn_hash=}")


@time_execution
async def publish_to_ipfs(
    rfid_card_id: str, local_file_path: tp.Optional[str] = None, remote_file_path: tp.Optional[str] = None
) -> tp.Tuple[str, str]:
    """publish a provided file to IPFS using the Feecc gateway and return it's CID and URL"""
    gateway_is_up()

    url = f"{IO_GATEWAY_ADDRESS}/io-gateway/ipfs"
    headers: tp.Dict[str, str] = get_headers(rfid_card_id)

    if local_file_path is not None:
        with open(local_file_path, "rb") as f:
            form_data: tp.Dict[str, tp.Union[tp.Optional[str], tp.BinaryIO]] = {"file_data": f}
    else:
        form_data = {"filename": remote_file_path}

    async with httpx.AsyncClient() as client:
        response: httpx.Response = await client.post(url=url, headers=headers, data=form_data)

    if response.is_error:
        raise httpx.RequestError(response.text)

    cid: str = response.json()["ipfs_cid"]
    link: str = response.json()["ipfs_link"]

    logger.info(f"File '{local_file_path or remote_file_path} published to IPFS under CID {cid}'")

    return cid, link


@time_execution
async def publish_to_pinata(
    rfid_card_id: str, local_file_path: tp.Optional[str] = None, remote_file_path: tp.Optional[str] = None
) -> tp.Tuple[str, str]:
    """publish a provided file to Pinata using the Feecc gateway and return it's CID and URL"""
    gateway_is_up()

    url = f"{IO_GATEWAY_ADDRESS}/io-gateway/pinata"
    headers: tp.Dict[str, str] = get_headers(rfid_card_id)

    if local_file_path is not None:
        with open(local_file_path, "rb") as f:
            form_data: tp.Dict[str, tp.Union[bool, tp.Optional[str], tp.BinaryIO]] = {
                "file_data": f,
                "background": True,
            }
    else:
        form_data = {"filename": remote_file_path, "background": True}

    async with httpx.AsyncClient() as client:
        response: httpx.Response = await client.post(url=url, headers=headers, data=form_data)

    if response.is_error:
        raise httpx.RequestError(response.text)

    cid: str = response.json()["ipfs_cid"]
    link: str = response.json()["ipfs_link"]

    logger.info(f"File {remote_file_path or local_file_path} published to Pinata under CID {cid}")

    return cid, link


@time_execution
async def publish_file(
    rfid_card_id: str, local_file_path: tp.Optional[str] = None, remote_file_path: tp.Optional[str] = None
) -> tp.Optional[tp.Tuple[str, str]]:
    """publish a file to pinata or IPFS according to config"""
    if config.pinata.enable:
        return await publish_to_pinata(rfid_card_id, local_file_path, remote_file_path)  # type: ignore
    elif config.ipfs.enable:
        return await publish_to_ipfs(rfid_card_id, local_file_path, remote_file_path)  # type: ignore
    else:
        logger.warning(
            f"File '{local_file_path or remote_file_path}' is neither published to Pinata, nor IPFS as both options are disabled"
        )
        return None


@time_execution
async def print_image(file_path: str, rfid_card_id: str, annotation: tp.Optional[str] = None) -> None:
    """print the provided image file"""
    gateway_is_up()

    async with httpx.AsyncClient() as client:
        url = f"{IO_GATEWAY_ADDRESS}/printing/print_image"
        headers: tp.Dict[str, str] = get_headers(rfid_card_id)

        with open(file_path, "rb") as f:
            form_data = {
                "image_file": f,
                "annotation": annotation,
            }
            response: httpx.Response = await client.post(url=url, headers=headers, data=form_data)

    if response.is_error:
        raise httpx.RequestError(response.text)

    logger.info(f"Printed image '{file_path}'")
