import importlib
import pathlib
import sys

from zeus.application import Application


def __config_validator(config: dict):
    return True


def main(name: str = "trader", config_path: pathlib.Path = pathlib.Path()) -> None:
    """Import the 'Trader' class from the named module and run it."""
    app = Application(name, config_path, __config_validator)

    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    mod = importlib.import_module(name)
    trader = mod.Trader(app.config["trader"], app.event_loop)  # type: ignore

    app.event_loop.create_task(trader.run())
    app.run()
