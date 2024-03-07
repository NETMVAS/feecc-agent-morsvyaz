from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class MongoDB(BaseModel):
    uri: str
    db_name: str

class RobonomicsNetwork(BaseModel):
    enable_datalog: bool
    account_seed: str
    substrate_node_uri: str

class IPFSGateway(BaseModel):
    enable: bool
    ipfs_server_uri: str

class Printer(BaseModel):
    enable: bool 
    paper_aspect_ratio: str 
    print_barcode: bool
    print_qr: bool
    print_qr_only_for_composite: bool
    print_security_tag: bool
    security_tag_add_timestamp: bool

class Camera(BaseModel):
    enable: bool
    ffmpeg_command: str

class Workbench(BaseModel):
    number: int
    login: bool
    dummy_employee: str

class BusinessLogic(BaseModel):
    start_uri: str
    manual_input_uri: str
    stop_uri: str

class HidDevices(BaseModel):
    rfid_reader: str
    barcode_reader: str

class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter='__')

    language_message: str

    mongodb: MongoDB
    robonomics: RobonomicsNetwork
    ipfs_gateway: IPFSGateway
    printer: Printer
    camera: Camera
    workbench: Workbench
    business_logic: BusinessLogic
    hid_devices: HidDevices


CONFIG = _Settings()