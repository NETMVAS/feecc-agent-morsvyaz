import os
import pathlib
import sys
from collections.abc import Iterable

import environ
from dotenv import load_dotenv
from loguru import logger

dotenv_file = pathlib.Path("../.env")
if dotenv_file.exists():
    load_dotenv(dotenv_file)
    logger.info(f"Loaded env vars from file '{dotenv_file.absolute()}'")


@environ.config(prefix="", frozen=True)
class AppConfig:
    @environ.config(frozen=True)
    class ChooseLang:
        choose_lang: str = environ.var(name="LANGUAGE_MESSAGE", help='Message language')
    @environ.config(frozen=True)
    class MongoDB:
        mongo_connection_uri: str = environ.var(name="MONGODB_URI", help="Your MongoDB connection URI")
        mongo_db_name: str = environ.var(name="MONGODB_DB_NAME", help="Your MongoDB DB name")

    @environ.config(frozen=True)
    class RobonomicsNetwork:
        enable_datalog: bool = environ.bool_var(default=False, help="Whether to enable datalog posting or not")
        account_seed: str | None = environ.var(default=None, help="Your Robonomics network account seed phrase")
        substrate_node_uri: str | None = environ.var(default=None, help="Robonomics network node URI")

    @environ.config(frozen=True)
    class IPFSGateway:
        enable: bool = environ.bool_var(default=False, help="Whether to enable IPFS posting or not")
        ipfs_server_uri: str = environ.var(default="http://127.0.0.1:8083", help="Your IPFS gateway deployment URI")

    @environ.config(frozen=True)
    class Printer:
        enable: bool = environ.bool_var(default=False, help="Whether to enable printing or not")
        paper_aspect_ratio: str = environ.var(default=False, help="Printer labels aspect ratio (size in mm in "
                                                                       "form of width:height)")
        print_barcode: bool = environ.bool_var(default=True, help="Whether to print barcodes or not")
        print_qr: bool = environ.bool_var(default=True, help="Whether to print QR codes or not")
        print_qr_only_for_composite: bool = environ.bool_var(
            default=False, help="Whether to enable QR code printing for non-composite units or note or not"
        )
        print_security_tag: bool = environ.bool_var(
            default=False, help="Whether to enable printing security tags or not"
        )
        security_tag_add_timestamp: bool = environ.bool_var(
            default=True, help="Whether to enable timestamps on security tags or not"
        )

    @environ.config(frozen=True)
    class Camera:
        enable: bool = environ.bool_var(name="CAMERA_ENABLE", help="Whether to enable Camera or not")
        ffmpeg_command: str = environ.var(name="CAMERA_FFMPEG_COMMAND", help="FFMPEG record command")

    @environ.config(frozen=True)
    class WorkBenchConfig:
        number: int = environ.var(converter=int, help="Workbench number")

    @environ.config(frozen=True)
    class HidDevicesNames:
        rfid_reader: str = environ.var(default="rfid_reader", help="RFID reader device name")
        barcode_reader: str = environ.var(default="barcode_reader", help="Barcode reader device name")

    lang = environ.group(ChooseLang)
    db = environ.group(MongoDB)
    robonomics = environ.group(RobonomicsNetwork)
    ipfs_gateway = environ.group(IPFSGateway)
    printer = environ.group(Printer)
    camera = environ.group(Camera)
    workbench = environ.group(WorkBenchConfig)
    hid_devices = environ.group(HidDevicesNames)


def export_docker_secrets(secret_names: Iterable[str]) -> None:
    """
    Export all the requested docker secrets into the environment

    A secret and the corresponding variable are expected to have the same name,
    but uppercase for the variable and lowercase for the secret file.
    """
    for secret in secret_names:
        secret_path = pathlib.Path(f"/run/secrets/{secret.lower()}")
        if not secret_path.exists():
            continue
        with secret_path.open() as f:
            content = f.read()
        os.environ[secret.upper()] = content
        logger.debug(f"Loaded up {secret.upper()} secret from Docker secrets")


if __name__ == "__main__":
    print(environ.generate_help(AppConfig))  # noqa: T201

try:
    docker_secrets = ["mongodb_uri", "robonomics_account_seed", "yourls_username", "yourls_password"]
    export_docker_secrets(docker_secrets)
    CONFIG = environ.to_config(AppConfig)
except environ.MissingEnvValueError as e:
    logger.critical(f"Missing required environment variable '{e}'. Exiting.")
    sys.exit(1)
