#!/usr/bin/env python3
"""Append the latest BTC, ETH, and SOL dollar prices to the unit ledger.

The first successful run records startedAt. Later runs add one print per coin.
A failed fetch leaves the file untouched.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SYMBOLS = {
    "btc": "BTC-USD",
    "eth": "ETH-USD",
    "sol": "SOL-USD",
}


def fetch_price(symbol: str) -> float:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval=1d&range=5d"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Fami"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    result = payload["chart"]["result"][0]["meta"]
    price = result["regularMarketPrice"]
    if not isinstance(price, (int, float)) or price <= 0:
        raise RuntimeError(f"{symbol} had no price")
    return float(price)


def merge(ledger: dict | None, prices: dict[str, float], stamp: str) -> dict:
    book = ledger if isinstance(ledger, dict) else {}
    if not book.get("startedAt"):
        book["startedAt"] = stamp
    for key, price in prices.items():
        prints = book.get(key)
        if not isinstance(prints, list):
            prints = []
        prints.append({"t": stamp, "p": price})
        book[key] = prints
    book["asOf"] = stamp
    return book


def load(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save(path: Path, ledger: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(ledger, indent=2) + "\n")
    temporary.replace(path)


def stamp_now() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def publish(path: Path) -> bool:
    """Return True when a new print was saved. A failed fetch writes nothing."""
    try:
        prices = {key: fetch_price(symbol) for key, symbol in SYMBOLS.items()}
    except Exception as error:
        print(f"unit prices unchanged: {error}", file=sys.stderr)
        return False
    current = None
    if path.exists():
        try:
            current = load(path)
        except Exception as error:
            print(f"unit prices unchanged: {error}", file=sys.stderr)
            return False
    save(path, merge(current, prices, stamp_now()))
    return True


def self_test() -> None:
    first = merge(None, {"btc": 10.0, "eth": 20.0, "sol": 30.0}, "2026-10-25T00:00:00Z")
    assert first["startedAt"] == "2026-10-25T00:00:00Z"
    assert first["btc"] == [{"t": "2026-10-25T00:00:00Z", "p": 10.0}]
    second = merge(
        first,
        {"btc": 11.0, "eth": 21.0, "sol": 31.0},
        "2026-10-25T00:15:00Z",
    )
    assert second["startedAt"] == "2026-10-25T00:00:00Z"
    assert second["btc"][0]["p"] == 10.0
    assert second["btc"][1] == {"t": "2026-10-25T00:15:00Z", "p": 11.0}
    assert len(second["eth"]) == 2
    assert len(second["sol"]) == 2


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test()
        raise SystemExit(0)
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "unit_prices.json")
    raise SystemExit(0 if publish(destination) or destination.exists() else 1)
