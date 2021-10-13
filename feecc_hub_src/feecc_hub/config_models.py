import typing as tp

from pydantic import BaseModel


class ConfigSection(BaseModel):
    pass


class ApiServer(ConfigSection):
    ip: str
    port: int


class MongoDB(ConfigSection):
    mongo_connection_url: str


class RobonomicsNetwork(ConfigSection):
    enable_datalog: bool
    account_address: str
    account_seed: str
    substrate_node_url: str


class Pinata(ConfigSection):
    enable: bool


class Ipfs(ConfigSection):
    enable: bool


class Yourls(ConfigSection):
    server: str
    username: str
    password: str


class Printer(ConfigSection):
    printer_model: str
    paper_width: int
    enable: bool
    red: bool


class PrintBarcode(ConfigSection):
    enable: bool


class PrintQr(ConfigSection):
    enable: bool
    logos: bool


class PrintSecurityTag(ConfigSection):
    enable: bool
    enable_timestamp: bool


class HidDevices(ConfigSection):
    rfid_reader: str
    barcode_reader: str


class WorkBenchConfig(ConfigSection):
    number: int
    description: str
    api_socket: str
    feecc_io_gateway_socket: str
    hardware: tp.Dict[str, tp.Any]


class GlobalConfig(ConfigSection):
    api_server: ApiServer
    mongo_db: MongoDB
    robonomics_network: RobonomicsNetwork
    pinata: Pinata
    ipfs: Ipfs
    yourls: Yourls
    printer: Printer
    print_barcode: PrintBarcode
    print_qr: PrintQr
    print_security_tag: PrintSecurityTag
    workbench_config: WorkBenchConfig
    known_hid_devices: HidDevices
