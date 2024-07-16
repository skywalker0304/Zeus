import pathlib

from argparse import ArgumentParser

from zeus.traders import trader


def sample():
    pass


def backtest():
    pass


def hypertune():
    pass


def trade(args):
    trader.main(args.trader_name, args.trader_config)


def main() -> None:
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title="command")

    sample_parser = subparsers.add_parser("sample")
    sample_parser.add_argument("--sampling_config", "-s", type=pathlib.Path)
    sample_parser.set_defaults(func=sample)

    backtest_parser = subparsers.add_parser("backtest")
    backtest_parser.add_argument("--trader_name", "-n", type=str)
    backtest_parser.add_argument("--trader_config", "-tc", type=pathlib.Path)
    backtest_parser.add_argument("--backtest_config", "-bc", type=pathlib.Path)
    backtest_parser.set_defaults(func=backtest)

    hypertune_parser = subparsers.add_parser("hypertune")
    hypertune_parser.add_argument("--trader_name", "-n", type=str)
    hypertune_parser.add_argument("--trader_config", "-tc", type=pathlib.Path)
    hypertune_parser.add_argument(
        "--backtest_config", "-bc", type=pathlib.Path)
    hypertune_parser.add_argument(
        "--hypertune_config", "-cc", type=pathlib.Path)
    hypertune_parser.set_defaults(func=hypertune)

    trade_parser = subparsers.add_parser("trade")
    trade_parser.add_argument("--trader_name", "-n", type=str)
    trade_parser.add_argument("--trader_config", "-tc", type=pathlib.Path)
    trade_parser.set_defaults(func=trade)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
