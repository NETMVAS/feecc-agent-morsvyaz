import logging
import threading
import typing as tp

import requests

import modules.external_io_operations as external_io
from Passport import Passport
from modules.Camera import Camera


class Agent:
    """Handles agent's state management and high level operation"""

    def __init__(self, config: tp.Dict[str, tp.Dict[str, tp.Any]], camera_config: tp.Dict[str, str]) -> None:
        """agent is initialized with state 0 and has an instance of Passport and Camera associated with it"""

        self._state = None
        self._state_thread: tp.Optional[threading.Thread] = None
        self.config: tp.Dict[str, tp.Dict[str, tp.Any]] = config
        self.backend_api_address: str = config["api_address"]["backend_api_address"]
        self.associated_passport: tp.Optional[Passport] = None
        self.associated_camera: Camera = Camera(camera_config)
        self.ipfsworker: external_io.ExternalIoGateway = external_io.ExternalIoGateway(self.config)
        self.latest_record_filename: str = ""
        self.latest_record_short_link: str = ""
        self.latest_record_qrpic_filename: str = ""

    @property
    def state(self) -> int:
        return self._state.number

    def execute_state(self, state, background: bool = True) -> None:
        """execute provided state in the background"""

        self._state = state(self)
        self._update_backend_state(priority=1)
        logging.info(f"Agent state is now {self._state.name}")

        if background:
            # execute state in the background
            self._state_thread = threading.Thread(target=self._state.run)
            self._state_thread.start()
        else:
            self._state.run()

    def _update_backend_state(self, priority: int = 1) -> None:
        """post an updated system state to the backend to keep it synced with the local state"""

        logging.info(f"Changing backend state to {self.state}")
        logging.debug(f"self.backend_api_address = {self.backend_api_address}")
        target_url = f"{self.backend_api_address}/state-update"
        payload = {
            "change_state_to": self.state,
            "priority": priority
        }

        logging.debug(f"Sending request to:\n {target_url}\nWith payload:\n{payload}")

        response = requests.post(
            url=target_url,
            json=payload
        )

        if response.status_code == 200:
            logging.info(f"Send backend state transition request: success")
        else:
            logging.error(f"backend state transition request failed: HTTP code {response.status_code}")
