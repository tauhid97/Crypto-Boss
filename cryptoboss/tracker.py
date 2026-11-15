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
    base = sig["fill_price"] if sig.get("order_type") in ("dip_bounce", "buy_now") else sig["entry"]
    risk = base - sig["stop"]                  # dip twins: risk from the real buy price
    sig.update(status=status, exit_price=float(price), exit_time=ts.isoformat(),
               r_multiple=round((out - fill) / risk, 3), pct_return=round((out / fill - 1) * 100, 3))
    return sig


# Crash Dip's "cool down" sell (from NostalgiaForInfinity): the more profit, the earlier we sell as RSI cools.
# (profit after the spread, sell once RSI is under this) - one table above the 200 line, one below it.
COOL_ABOVE = [(0.001, 10), (0.01, 28), (0.02, 30), (0.03, 32), (0.04, 34), (0.05, 36), (0.06, 38), (0.07, 40),
              (0.08, 42), (0.09, 44), (0.10, 46), (0.12, 44), (0.20, 42)]
COOL_BELOW = [(0.001, 12), (0.01, 30), (0.02, 32), (0.03, 34), (0.04, 36), (0.05, 38), (0.06, 40), (0.07, 42),
              (0.08, 44), (0.09, 46), (0.10, 48), (0.12, 46), (0.20, 44)]


def cooled(profit, rsi, above200):
    """True when a Crash Dip trade in profit has calmed down enough to sell."""
    gate = None
    for lim, g in (COOL_ABOVE if above200 else COOL_BELOW):
        if profit >= lim:
            gate = g
    return gate is not None and rsi == rsi and rsi < gate


def _window(sig, key, default):
    v = sig.get(key)
    return pd.Timedelta(v if isinstance(v, str) and v else default)


def settle(sig, bars, now):
    """Update one signal (dict) using candles; returns the same dict."""
    window, hold = _window(sig, "entry_window", C.ENTRY_WINDOW), _window(sig, "max_hold", C.MAX_HOLD)
    pub = pd.Timestamp(sig["published_at"])
    entry, stop, target = sig["entry"], sig["stop"], sig["target"]
    step = pd.Timedelta(C.CANDLE)
    filled_at = pd.Timestamp(sig["fill_time"]) if sig.get("status") == "open" else None
    dip = sig.get("order_type") == "dip_bounce"
    dipped = False
    cool = sig.get("exit_rule") == "cool_down"
    sell_next = False
    for ts, b in bars[bars.index >= pub].iterrows():
        if ts + step > now:
            break
        if filled_at is None:
            if ts >= pub + window:
                sig.update(status="no_fill", r_multiple=0.0, pct_return=0.0, exit_time=ts.isoformat())
                return sig
            if dip:                                    # dip twin: wait for a drop, then proof of a bounce
                dipped = dipped or b["Low"] <= entry
                if not dipped:
                    continue
                if b["Low"] <= stop:                   # kept falling to the safety price: never bought
                    sig.update(status="no_fill", r_multiple=0.0, pct_return=0.0, exit_time=ts.isoformat())
                    return sig
                if not (b["Close"] > b["Open"] and b["Close"] > entry and b["Close"] < target):
                    continue                           # no green candle back above the dip price yet
                filled_at = ts                         # bought at the bounce candle's close;
                sig.update(status="open", fill_time=ts.isoformat(), fill_price=float(b["Close"]))
                continue                               # selling starts with the next candle
            elif sig.get("order_type") == "buy_now":   # buy right away, at the next candle's opening price
                price = b["Open"]
            else:                                      # climb order: buy only when the price RISES to the entry
                if b["High"] < entry:
                    continue
                price = max(entry, b["Open"])
            filled_at = ts
            sig.update(status="open", fill_time=ts.isoformat(), fill_price=float(price))
            if b["Low"] <= stop:                       # stopped in the same candle we got in
                return _close(sig, stop, ts, "stop")
            continue
        if sell_next:                                  # it cooled down last candle: sell at this candle's open
            return _close(sig, b["Open"], ts, "target")
        if ts >= filled_at + hold:
            return _close(sig, b["Open"], ts, "timeout")
        if b["Low"] <= stop:
            return _close(sig, min(stop, b["Open"]), ts, "stop")
        if b["High"] >= target:
            return _close(sig, max(target, b["Open"]), ts, "target")
        if cool and "RSI" in b:
            profit = b["Close"] * (1 - C.SPREAD_PCT) / (sig["fill_price"] * (1 + C.SPREAD_PCT)) - 1
            sell_next = cooled(profit, b["RSI"], b["Close"] > b.get("EMA200", float("inf")))
    if filled_at is None and now >= pub + window + step:
        sig.update(status="no_fill", r_multiple=0.0, pct_return=0.0, exit_time=now.isoformat())
    return sig
