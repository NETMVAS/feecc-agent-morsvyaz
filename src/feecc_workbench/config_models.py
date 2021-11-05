import typing as tp

from pydantic import BaseModel


class ConfigSection(BaseModel):
    pass


class MongoDB(ConfigSection):
    mongo_connection_url: str


class FeeccIoGateway(ConfigSection):
    gateway_address: str
    autonomous_mode: bool


class RobonomicsNetwork(ConfigSection):
    enable_datalog: bool
    account_address: str
    account_seed: str
    substrate_node_url: tp.Optional[str]


class Yourls(ConfigSection):
    server: str
    username: str
    password: str


class Printer(ConfigSection):
    enable: bool
    print_barcode: bool
    print_qr: bool
    print_qr_only_for_composite: bool
    qr_add_logos: bool
    print_security_tag: bool
    security_tag_add_timestamp: bool


class WorkBenchConfig(ConfigSection):
    number: int
    description: str


class Hardware(ConfigSection):
    camera_no: tp.Optional[int]


class HidDevicesNames(ConfigSection):
    rfid_reader: str
    barcode_reader: str


class GlobalConfig(BaseModel):
    mongo_db: MongoDB
    feecc_io_gateway: FeeccIoGateway
    robonomics_network: RobonomicsNetwork
    yourls: Yourls
    printer: Printer
    workbench_config: WorkBenchConfig
    hardware: Hardware
    hid_devices_names: HidDevicesNames
