"""Free crypto prices from Coinbase's public API (no account, no key). Robinhood's prices follow them closely."""
import time

import pandas as pd
import requests

from . import config as C

URL = "https://api.exchange.coinbase.com/products/{}-USD/candles"
STEP = pd.Timedelta(C.CANDLE)


def _get(coin, start=None, end=None, step=STEP):
    params = {"granularity": int(step.total_seconds())}
    if start is not None:
        params.update(start=start.isoformat(), end=end.isoformat())
    for attempt in range(3):
        try:
            r = requests.get(URL.format(coin), params=params, timeout=15,
                             headers={"User-Agent": "crypto-boss-bot"})
            if r.status_code == 429:           # asked too fast - wait and try again
                time.sleep(2 * (attempt + 1))
                continue
            if not r.ok:
                return None
            rows = r.json()
            break
        except Exception as e:
            print(f"{coin}: download error ({e}); retrying...")
            time.sleep(2 * (attempt + 1))
    else:
        return None
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["time", "Low", "High", "Open", "Close", "Volume"])
    df.index = pd.to_datetime(df.pop("time"), unit="s", utc=True)
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index().astype(float)


def closed(frames, now):
    """Keep only candles that have finished (a half-done candle can fool the skills)."""
    out = {}
    for c, df in frames.items():
        df = df[df.index + STEP <= now]
        if len(df):
            out[c] = df
    return out


def get_all(coins, now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    out = {}
    for c in coins:
        df = _get(c)
        if df is not None:
            out[c] = df
        time.sleep(0.15)                       # be polite: Coinbase allows ~10 requests a second
    return closed(out, now)


def daily(coin):
    """The last 300 daily candles (UTC days) - for the day skills."""
    return _get(coin, step=pd.Timedelta("1D"))


def history(coin, days):
    """Older candles for the backtest (Coinbase gives 300 at a time)."""
    end = pd.Timestamp.now(tz="UTC").floor(STEP)
    start = end - pd.Timedelta(days=days)
    parts, t = [], start
    while t < end:
        t2 = min(t + STEP * 300, end)
        df = _get(coin, t, t2)
        if df is not None:
            parts.append(df)
        t = t2
        time.sleep(0.15)
    if not parts:
        return None
    df = pd.concat(parts)
    return df[~df.index.duplicated()].sort_index()
