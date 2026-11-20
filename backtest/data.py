"""Market-data loader — Nasdaq public historical API (no key required).

Why Nasdaq and not Yahoo Finance: from this environment Yahoo's API
answers HTTP 429 (rate-limited on the shared egress IP) and Stooq serves
a bot-challenge page, while Nasdaq's historical endpoint answers reliably.
If you run this on your own machine, you can swap in yfinance by
replacing :func:`download_data` — the rest of the code only needs the
``{'open','high','low','close','volume'}`` DataFrames it returns.

Data notes (important for interpreting results)
-----------------------------------------------
- Prices are split-adjusted but NOT dividend-adjusted, so total returns
  are slightly understated — roughly by each holding's dividend yield
  (SPY ~1.3%/yr). The understatement applies equally to every strategy
  and to the SPY benchmark, so strategy *comparisons* are still valid.
- Rows are trading days only. Dates are aligned to the SPY calendar;
  other symbols are forward-filled onto it.
- Raw per-symbol JSON responses are cached under ``data/raw/`` so a
  re-run does not re-download everything.
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.nasdaq.com/api/quote/{symbol}/historical"
ETFS = {"SPY", "QQQ", "TLT", "BIL"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}


def _clean_num(value) -> float:
    if value is None:
        return float("nan")
    text = str(value).replace("$", "").replace(",", "").strip()
    if text in ("", "N/A", "NA", "--"):
        return float("nan")
    return float(text)


def download_symbol(
    symbol: str,
    start: str = "2021-01-01",
    end: str = "2026-11-20",
    cache_dir: Path | None = None,
    sleep_s: float = 0.5,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Daily OHLCV for one symbol, oldest first, indexed by date."""
    cache_file = None
    if cache_dir is not None:
        cache_file = Path(cache_dir) / f"{symbol}.json"
        if use_cache and cache_file.exists():
            raw = json.loads(cache_file.read_text())
        else:
            raw = None
    else:
        raw = None
    if raw is None:
        resp = requests.get(
            BASE_URL.format(symbol=symbol),
            params={
                "assetclass": "etf" if symbol in ETFS else "stocks",
                "fromdate": start,
                "todate": end,
                "limit": 9999,
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(raw))
        time.sleep(sleep_s)
    rows = (raw.get("data") or {}).get("tradesTable", {}).get("rows") or []
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].map(_clean_num)
    df["volume"] = df["volume"].map(_clean_num)
    return df.sort_values("date").set_index("date")


def download_data(
    symbols: list[str],
    start: str = "2021-01-01",
    end: str = "2026-11-20",
    cache_dir: Path | None = None,
) -> dict:
    """Download OHLCV for all symbols; return dict of DataFrames.

    Keys are 'open', 'high', 'low', 'close', 'volume'. All frames share
    the SPY trading calendar; missing values are forward-filled.
    """
    per_symbol = {
        s: download_symbol(s, start, end, cache_dir) for s in symbols
    }
    closes = pd.DataFrame({s: per_symbol[s]["close"] for s in symbols})
    closes = closes[closes["SPY"].notna()]
    frames = {}
    for field in ["open", "high", "low", "close", "volume"]:
        frames[field] = pd.DataFrame(
            {s: per_symbol[s][field] for s in symbols}
        ).reindex(closes.index).ffill()
    return frames
