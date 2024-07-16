import time

from zeus.types import Instrument
from .websocket_client import WebSocketClient, WebSocketHelper


class Recorder(WebSocketClient):
    """A class for recording market data."""

    def __init__(self, buffer: list, config: dict, idx: int, ins: Instrument):
        """Initialize a new instance of the BaseExchange class."""
        self.buffer = buffer
        self.idx = idx
        self.next_recv_ts_ns = time.time_ns(
        ) + config["recv_interval"] * 1_000_000
        self.recv_interval = config["recv_interval"] * 1_000_000
        super().__init__(WebSocketHelper(ins.get_host(), ins.get_port(), ins.get_path()))

    def on_message(self) -> None:
        """Callback when an individual message has been received."""
        self.buffer[self.idx] += self._payload
        self.buffer[self.idx] += b"\x00"

    def on_data_end(self) -> None:
        """Callback when data_received has been sucessfully processed."""
        self.next_recv_ts_ns = time.time_ns() + self.recv_interval
