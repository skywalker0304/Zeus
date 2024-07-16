import asyncio
import base64
import enum
import hashlib
import logging
import secrets
import time

from typing import Optional

FRAME_HEADER_SIZE: int = 2
FRAME_MASK: bytes = b"\x00" * 4
MAGIC: bytes = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


@enum.unique
class _WebSocketFrameType(enum.IntEnum):
    CONT = 0
    TEXT = 1
    BIN = 2
    CLOSE = 8
    PING = 9
    PONG = 10


class WebSocketHelper:
    """A HTTP/1.1 websocket helper."""
    __slots__ = ("closing_handshake", "host", "opening_handshake",
                 "port", "path", "__accept", "__key")

    def __init__(self, host: str = "", port: int = 443, path: str = "") -> None:
        """Initialize a new instance of the WebSocketHelper class."""
        self.__key: bytes = base64.b64encode(secrets.token_bytes(16))
        self.__accept: bytes = base64.b64encode(
            hashlib.sha1(self.__key + MAGIC).digest())

        self.opening_handshake: bytes = b"GET /" + path.encode() + b" HTTP/1.1\r\nHost: " + host.encode() + \
            b"\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: " + \
            self.__key + b"\r\nSec-WebSocket-Version: 13\r\n\r\n"
        self.closing_handshake: bytes = b"\x88\x80"
        self.host = host
        self.port = port
        self.path = path

    def __str__(self):
        """Return a string containing a description of this order object."""
        return f"{self.host}:{self.port}/{self.path}"

    def pack(self, typ: _WebSocketFrameType, data: bytes) -> bytes:
        """Pack a payload with mask is b'\x00' * 32 to avoid xor."""
        data_length = len(data)
        header = (128 + typ).to_bytes(length=1, byteorder="big", signed=False)
        if data_length < 126:
            header += (128 + data_length).to_bytes(length=1,
                                                   byteorder="big", signed=False)
        elif data_length < 65536:
            header += b"\xfe"
            header += data_length.to_bytes(length=2,
                                           byteorder="big", signed=False)
        else:
            header += b"\xff"
            header += data_length.to_bytes(length=8,
                                           byteorder="big", signed=False)
        header += FRAME_MASK + data
        return header

    def unpack_from(self, data: bytes, start: int) -> tuple[_WebSocketFrameType, int, bool]:
        """Unpack websocket frame header to type, length, and final."""
        if data[start] & 112:
            raise ValueError("expected 0 for RSV1, RSV2, RSV3")
        typ = _WebSocketFrameType(data[start] & 15)
        length = data[start+1] & 127
        match length:
            case 126:
                if len(data) - start > FRAME_HEADER_SIZE + 2:
                    length = int.from_bytes(
                        data[start+2:start+4], byteorder="big", signed=False)
                    return (typ, length, bool(data[start] & 128))
            case 127:
                if len(data) - start > FRAME_HEADER_SIZE + 8:
                    length = int.from_bytes(
                        data[start+2:start+10], byteorder="big", signed=False)
                    return (typ, length, bool(data[start] & 128))
            case _:
                return (typ, length, bool(data[start] & 128))
        return (typ, -1, bool(data[start] & 128))

    def check_handshake(self, data: bytes) -> bool:
        """Validate response from websocket opening handshake."""
        response = data.decode().split("\r\n")
        if response[0] != "HTTP/1.1 101 Switching Protocols":
            return False
        for line in response[1:]:
            key, value = line.split(": ", 2)
            if key.lower() == "sec-websocket-accept":
                return value.encode() == self.__accept
        return False


class WebSocketClient(asyncio.Protocol):
    """A stream-based websocket connection."""

    def __init__(self, wshelper: WebSocketHelper) -> None:
        """Initialize a new instance of the WebSocketClient class."""
        self._accpet: str = ""
        self._closing: bool = False
        self._connection_transport: Optional[asyncio.transports.Transport] = None
        self._data: bytes = b""
        self._file_number: int = 0
        self._payload: bytes = b""
        self._wshandshake: bool = True
        self._wshelper = wshelper
        self._wsping: bytes = b""

        self.__logger = logging.getLogger("WebSocketClient")

    def close(self) -> None:
        """Close the connection."""
        self.__logger.debug("fd=%d close connection", self._file_number)
        self._closing = True
        if self._connection_transport is not None and not self._connection_transport.is_closing():
            if not self._wshandshake:
                self.send_data(self._wshelper.closing_handshake)
            self._connection_transport.close()

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Callback when a connection has been lost."""
        if exc is not None:
            self.__logger.error("fd=%d connection lost",
                                self._file_number, exc_info=exc)
        else:
            self.__logger.error("fd=%d connection lost", self._file_number)
        self._connection_transport = None

    def connection_made(self, transport: asyncio.transports.BaseTransport) -> None:
        """Callback when a connection has been established."""
        sock = transport.get_extra_info("socket")
        if sock is not None:
            self._file_number = sock.fileno()
        self.__logger.info("fd=%d connection made: peer=%s:%d", self._file_number,
                            *(transport.get_extra_info("peername") or ("unknown", 0)))
        self._connection_transport = transport  # type: ignore
        self.send_data(self._wshelper.opening_handshake)

    def data_received(self, data: bytes) -> None:
        """Callback when data is received."""
        self.__logger.debug("fd=%d data received: %s", self._file_number, data)
        if self._wshandshake:
            if self._wshelper.check_handshake(data):
                self._wshandshake = False
            else:
                self.close()
            return

        if self._data:
            self._data += data
        else:
            self._data = data

        upto, data_length = 0, len(self._data)
        while not self._closing and upto < data_length - FRAME_HEADER_SIZE:
            try:
                typ, length, final = self._wshelper.unpack_from(
                    self._data, upto)
                if length == -1 or upto + FRAME_HEADER_SIZE + length > data_length:
                    break
                elif length < 126:
                    self.frame_received(
                        typ, upto + FRAME_HEADER_SIZE, length, final)
                    upto += FRAME_HEADER_SIZE + length
                elif length < 65536:
                    if upto + FRAME_HEADER_SIZE + 2 + length > data_length:
                        break
                    self.frame_received(
                        typ, upto + FRAME_HEADER_SIZE + 2, length, final)
                    upto += FRAME_HEADER_SIZE + 2 + length
                else:
                    if upto + FRAME_HEADER_SIZE + 8 + length > data_length:
                        break
                    self.frame_received(
                        typ, upto + FRAME_HEADER_SIZE + 8, length, final)
                    upto += FRAME_HEADER_SIZE + 8 + length
            except Exception as exc:
                self.__logger.error(
                    "fd=%d cannot unpack data to websocket frame", self._file_number, exc_info=exc)
                self.close()
        self._data = self._data[upto:]
        self.on_data_end()

    def frame_received(self, typ: int, start: int, length: int, final: bool) -> None:
        """Callback when a frame has been received."""
        self.__logger.debug("fd=%d frame received: %s",
                            self._file_number, self._data[start: start + length])
        self._payload += self._data[start:start + length]
        if final:
            match typ:
                case _WebSocketFrameType.TEXT | _WebSocketFrameType.BIN:
                    self.on_message()
                case _WebSocketFrameType.CLOSE:
                    if len(self._payload) != 0:
                        self.__logger.debug("fd=%d websocket close: reason=%d:%s", self._file_number, int.from_bytes(
                            self._payload[:2], byteorder="big", signed=False), self._payload[2:])
                    else:
                        self.__logger.debug(
                            "fd=%d websocket close", self._file_number)
                    self.close()
                case _WebSocketFrameType.PING:
                    self.on_ping()
                case _WebSocketFrameType.PONG:
                    self.on_pong()
                case _:
                    self.__logger.error(
                        "fd=%d receive wrong websocket frame type", self._file_number)
                    self.close()
            self._payload = b""

    def on_data_end(self) -> None:
        """Callback when data_received has been sucessfully processed."""

    def on_message(self) -> None:
        """Callback when an individual message has been received."""

    def on_ping(self) -> None:
        """Callback when a ping frame has been received."""
        self.pong(self._payload)

    def on_pong(self) -> None:
        """Callback when a pong frame has been received."""
        if self._wsping == b"":
            return
        elif self._payload == self._wsping:
            self._wsping = b""
        else:
            self.__logger.error(
                "fd=%d receive unmatch pong frame", self._file_number)
            self.close()

    def ping(self, payload: bytes = b"") -> None:
        """Send a ping frame to websocket server."""
        if self._wsping == b"":
            self._wsping = payload if payload != b"" else str(
                time.time_ns() // 1_000_000).encode()
            self.__logger.debug("fd=%d send ping frame: %s",
                                self._file_number, self._wsping)
            self.send_message(_WebSocketFrameType.PING, self._wsping)

    def pong(self, payload: bytes = b"") -> None:
        """Send a pong frame to websocket server."""
        self.__logger.debug("fd=%d send pong frame: %s",
                            self._file_number, payload)
        self.send_message(_WebSocketFrameType.PONG, payload)

    def send_data(self, data: bytes) -> None:
        """Send a data effeciently while risky."""
        if self._connection_transport is not None and not self._connection_transport.is_closing():
            self.__logger.debug("fd=%d send message: %s",
                                self._file_number, data)
            self._connection_transport.write(data)  # type: ignore

    def send_message(self, typ: _WebSocketFrameType, payload: bytes) -> None:
        """Pack a payload to websocket frames and send."""
        self.send_data(self._wshelper.pack(typ, payload))


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    async def main():
        wshelper = WebSocketHelper(
            "fstream.binance.com", 443, "stream?streams=btcusdt@markPrice@1s")
        loop = asyncio.get_event_loop()
        for _ in range(3):
            try:
                print(f"Create connection to {wshelper.host}")
                connection = WebSocketClient(wshelper)
                async with asyncio.timeout(5):
                    await loop.create_connection(lambda: connection, wshelper.host, wshelper.port, ssl=True, ssl_handshake_timeout=3, ssl_shutdown_timeout=3)
                for __ in range(3):
                    await asyncio.sleep(3)
                    connection.ping()
                connection.close()
                break
            except TimeoutError:
                print(f"Cannot create connection to {wshelper.host}")
            except Exception as exc:
                print(exc)
            finally:
                await asyncio.sleep(3)
        loop.stop()

    loop = asyncio.get_event_loop()
    loop.create_task(main())
    try:
        loop.run_forever()
    except Exception as exc:
        print(exc)
    finally:
        print("Closing event loop")
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            loop.close()
