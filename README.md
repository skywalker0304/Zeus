# Zeus

#### Dependencies

- Python 3.11.6
- Formatter `autopep8`
- `pip install -r requirements.txt`

#### Run
- Trade
```
python3 main.py trade --trader_name name --trader_config config.json
```

#### Config
```
{
    "trader": {
        "prometheus": {
            "output_path": "/data", # path
            "recorder": {
                "recv_interval": 1000, # milliseconds
            },
        },
        "maximum_reconnect_tries": 3, # times
        "create_connection_timeout": 3, # seconds
        "ssl_handshake_timeout": 3, # seconds
        "ssl_shutdown_timeout": 3, # seconds
        "check_ping_interval": 3, # seconds
        "check_recv_interval": 30, # seconds
        "reconnect_cooldown": 3, # seconds
        "instrument": [
            {"exchange": "binance-futures", "symbol": "BTCUSDT"},
            {"exchange": "binance-futures", "symbol": "ETHUSDT"},
            {"exchange": "binance-futures", "symbol": "SOLUSDT"},
            {"exchange": "binance-futures", "symbol": "DOGEUSDT"},
            {"exchange": "binance-futures", "symbol": "XRPUSDT"},
            {"exchange": "binance-futures", "symbol": "ADAUSDT"},
        ],
    }
}
```
