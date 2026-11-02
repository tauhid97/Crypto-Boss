"""JUDGE - follows each signal candle by candle and decides how it ended.

Strict rules: only candles that START after the signal was sent count; if the stop and the
target could both have been hit in one candle, we count the loss; Robinhood's spread is
taken off every trade.
"""
import pandas as pd

from . import config as C

ACTIVE = {"pending", "open"}


def _close(sig, price, ts, status):
    fill = sig["fill_price"] * (1 + C.SPREAD_PCT)
    out = price * (1 - C.SPREAD_PCT)
    risk = sig["entry"] - sig["stop"]
    sig.update(status=status, exit_price=float(price), exit_time=ts.isoformat(),
               r_multiple=round((out - fill) / risk, 3), pct_return=round((out / fill - 1) * 100, 3))
    return sig


def settle(sig, bars, now):
    """Update one signal (dict) using candles; returns the same dict."""
    pub = pd.Timestamp(sig["published_at"])
    entry, stop, target = sig["entry"], sig["stop"], sig["target"]
    step = pd.Timedelta(C.CANDLE)
    filled_at = pd.Timestamp(sig["fill_time"]) if sig.get("status") == "open" else None
    for ts, b in bars[bars.index >= pub].iterrows():
        if ts + step > now:
            break
        if filled_at is None:
            if ts >= pub + pd.Timedelta(C.ENTRY_WINDOW):
                sig.update(status="no_fill", r_multiple=0.0, pct_return=0.0, exit_time=ts.isoformat())
                return sig
            if b["High"] < entry:
                continue
            filled_at = ts
            sig.update(status="open", fill_time=ts.isoformat(), fill_price=float(max(entry, b["Open"])))
            if b["Low"] <= stop:                       # stopped in the same candle we got in
                return _close(sig, stop, ts, "stop")
            continue
        if ts >= filled_at + pd.Timedelta(C.MAX_HOLD):
            return _close(sig, b["Open"], ts, "timeout")
        if b["Low"] <= stop:
            return _close(sig, min(stop, b["Open"]), ts, "stop")
        if b["High"] >= target:
            return _close(sig, max(target, b["Open"]), ts, "target")
    if filled_at is None and now >= pub + pd.Timedelta(C.ENTRY_WINDOW) + step:
        sig.update(status="no_fill", r_multiple=0.0, pct_return=0.0, exit_time=now.isoformat())
    return sig
