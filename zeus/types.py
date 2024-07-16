import dataclasses
import enum
import hashlib


class Instrument:
    __slots__ = ("exchange", "symbol", "name", "hash")

    def __init__(self, exchange: str, symbol: str):
        """Initialize a new instance of the Instrument class."""
        self.exchange: str = exchange.lower()
        self.symbol: str = symbol.upper()
        self.name: str = self.exchange + "." + self.symbol
        self.hash: str = hashlib.sha256(self.name.encode()).hexdigest()[:8]

    def __str__(self):
        """Return a string containing a description of this order object."""
        return self.name

    def get_host(self) -> str:
        """Return the hostname of corresponding exchange."""
        match self.exchange:
            case "binance":
                return "stream.binance.com"
            case "binance-futures":
                return "fstream.binance.com"
        return "127.0.0.1"

    def get_port(self) -> int:
        """Return the websocket port of corresponding exchange."""
        return 443

    def get_path(self) -> str:
        """Return the websocket path of corresponding exchange."""
        match self.exchange:
            case "binance":
                return "stream?streams=%s@bookTicker/%s@trade/%s@depth@100ms" % (3 * (self.symbol.lower(),))
            case "binance-futures":
                return "stream?streams=%s@bookTicker/%s@trade/%s@depth@100ms/%s@markPrice@1s" % (4 * (self.symbol.lower(),))
        return ""


class Side(enum.IntEnum):
    SELL = 0
    BUY = 1
    ASK = SELL
    BID = BUY
    A = SELL
    B = BUY


class Lifespan(enum.IntEnum):
    FILL_AND_KILL = 0
    GOOD_FOR_DAY = 1
    IMMEDIATE_OR_CANCEL = FILL_AND_KILL
    LIMIT_ORDER = GOOD_FOR_DAY
    FAK = FILL_AND_KILL
    IOC = FILL_AND_KILL
    GFD = GOOD_FOR_DAY
    F = FILL_AND_KILL
    G = GOOD_FOR_DAY


class MarketMessageType(enum.IntEnum):
    ERROR = 0
    BOOK_TICKS = 1
    TRADE_TICKS = 2
    ORDER_BOOK_UPDATE = 3


class UserMessageType(enum.IntEnum):
    ACCOUNT_UPDATE = 0
    ORDER_STATUS = 1
    ORDER_FILLED = 2


@dataclasses.dataclass
class Order:
    price: float = 0
    size: float = 0
    ts_ms: int = 0
    is_l1: bool = False


@dataclasses.dataclass
class Trade:
    ts_ms: int
    trade_id: int
    price: float
    size: float
    side: Side


if __name__ == "__main__":
    instrument = Instrument("binance-FUTURES", "BTCusdt")
    print(instrument, instrument.hash)
    print(instrument.get_host())
    print(instrument.get_port())
    print(instrument.get_path())
