import pydantic
import yaml
from loguru import logger

from .config_models import GlobalConfig


@logger.catch
def _load_config(config_path: str) -> GlobalConfig:
    logger.debug(f"Looking for config in {config_path}")

    with open(config_path) as f:
        config_f = yaml.load(f.read(), Loader=yaml.SafeLoader)
        return pydantic.parse_obj_as(GlobalConfig, config_f)


config: GlobalConfig = _load_config("config/config.yaml")
