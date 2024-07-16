import asyncio
import logging
import pathlib
import time
import zlib

import aiofiles

from zeus.exchanges import Recorder
from zeus.types import Instrument


class Trader:
    def __init__(self, config: dict, loop: asyncio.AbstractEventLoop):
        self.buffer: list[bytes] = []
        self.config = config
        self.logger = logging.getLogger("Prometheus")
        self.loop = loop
        self.output_path: list[pathlib.Path] = []

    async def __run_recorder(self, idx: int, ins: Instrument):
        for _ in range(self.config["maximum_reconnect_tries"]):
            try:
                self.logger.info("Create connection to %s", ins.get_host())
                async with asyncio.timeout(self.config["create_connection_timeout"]):
                    recorder = Recorder(
                        self.buffer, self.config["prometheus"]["recorder"], idx, ins)
                    await self.loop.create_connection(lambda: recorder, ins.get_host(), ins.get_port(), ssl=True, ssl_handshake_timeout=self.config["ssl_handshake_timeout"], ssl_shutdown_timeout=self.config["ssl_shutdown_timeout"])
                while True:
                    if time.time_ns() > recorder.next_recv_ts_ns:
                        recorder.ping()
                        await asyncio.sleep(self.config["check_ping_interval"])
                        if time.time_ns() > recorder.next_recv_ts_ns:
                            recorder.close()
                            break
                    await asyncio.sleep(self.config["check_recv_interval"])
            except TimeoutError:
                self.logger.error("create connection timeout exceeded")
            except OSError as exc:
                self.logger.error("create connection failed: %s", exc.strerror)
            except Exception as exc:
                self.logger.error("unexpected exception", exc_info=exc)
            finally:
                await asyncio.sleep(self.config["reconnect_cooldown"])
        self.loop.stop()

    async def run(self):
        output_path = pathlib.Path(self.config["prometheus"]["output_path"])
        output_path.mkdir(parents=True, exist_ok=True)
        for idx, ins_config in enumerate(self.config["instrument"]):
            ins = Instrument(ins_config["exchange"], ins_config["symbol"])
            self.buffer.append(b"")
            self.loop.create_task(self.__run_recorder(idx, ins))
            path = output_path / str(ins)
            path.mkdir(parents=True, exist_ok=True)
            self.output_path.append(path)

        first_time = True
        while True:
            cur_time = time.time_ns() / 1_000_000_000
            remainder = 60 - cur_time % 60
            await asyncio.sleep(remainder - 0.0001)
            if not first_time:
                cur_time = time.time_ns() // 1_000_000_000
                cur_time -= cur_time % 60
                for idx, path in enumerate(self.output_path):
                    length = len(self.buffer[idx])
                    filename = path / str(cur_time)
                    async with aiofiles.open(filename, mode="wb") as f:
                        await f.write(zlib.compress(self.buffer[idx][:length]))
                    self.buffer[idx] = self.buffer[idx][length:]
            else:
                first_time = False
                for idx in range(len(self.buffer)):
                    self.buffer[idx] = b""
