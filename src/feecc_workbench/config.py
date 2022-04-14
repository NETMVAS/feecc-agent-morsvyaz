import sys
import typing as tp

import environ
from loguru import logger


@environ.config(prefix="", frozen=True)
class AppConfig:

    @environ.config(frozen=True)
    class MongoDB:
        mongo_connection_uri: str = environ.var(help="Your MongoDB connection URI")

    @environ.config(frozen=True)
    class RobonomicsNetwork:
        enable_datalog: bool = environ.bool_var(default=False, help="Whether to enable datalog posting or not")
        account_seed: tp.Optional[str] = environ.var(default=None, help="Your Robonomics network account seed phrase")
        substrate_node_uri: tp.Optional[str] = environ.var(default=None, help="Robonomics network node URI")

    @environ.config(frozen=True)
    class Yourls:
        server: str = environ.var(help="Your Yourls server URL")
        username: str = environ.var(help="Your Yourls server username")
        password: str = environ.var(help="Your Yourls server password")

    @environ.config(frozen=True)
    class IPFSGateway:
        enable: bool = environ.bool_var(default=False, help="Whether to enable IPFS posting or not")
        ipfs_server_uri: str = environ.var(default="http://127.0.0.1:8083", help="Your IPFS gateway deployment URI")

    @environ.config(frozen=True)
    class Printer:
        enable: bool = environ.bool_var(default=False, help="Whether to enable printing or not")
        print_server_uri: str = environ.var(default="http://127.0.0.1:8083", help="Your Print-server deployment URI")
        print_barcode: bool = environ.bool_var(default=True, help="Whether to print barcodes or not")
        print_qr: bool = environ.bool_var(default=True, help="Whether to print QR codes or not")
        print_qr_only_for_composite: bool = environ.bool_var(
            default=False, help="Whether to enable QR code printing for non-composite units or note or not"
        )
        qr_add_logos: bool = environ.bool_var(default=False, help="Whether to add logos to the QR code or not")
        print_security_tag: bool = environ.bool_var(
            default=False, help="Whether to enable printing security tags or not"
        )
        security_tag_add_timestamp: bool = environ.bool_var(
            default=True, help="Whether to enable timestamps on security tags or not"
        )

    @environ.config(frozen=True)
    class Camera:
        enable: bool = environ.bool_var(default=False, help="Whether to enable Cameraman or not")
        cameraman_uri: str = environ.var(default="http://127.0.0.1:8081", help="Your Cameraman deployment URI")
        camera_no: tp.Optional[int] = environ.var(default=None, converter=int, help="Camera number")

    @environ.config(frozen=True)
    class WorkBenchConfig:
        number: int = environ.var(converter=int, help="Workbench number")

    @environ.config(frozen=True)
    class HidDevicesNames:
        rfid_reader: str = environ.var(default="rfid_reader", help="RFID reader device name")
        barcode_reader: str = environ.var(default="barcode_reader", help="Barcode reader device name")

    db = environ.group(MongoDB)
    robonomics = environ.group(RobonomicsNetwork)
    yourls = environ.group(Yourls)
    ipfs_gateway = environ.group(IPFSGateway)
    printer = environ.group(Printer)
    camera = environ.group(Camera)
    workbench = environ.group(WorkBenchConfig)
    hid_devices = environ.group(HidDevicesNames)


if __name__ == "__main__":
    print(environ.generate_help(AppConfig))

try:
    Config = environ.to_config(AppConfig)
except environ.MissingEnvValueError as e:
    logger.critical(f"Missing required environment variable '{e}'. Exiting.")
    sys.exit(1)
