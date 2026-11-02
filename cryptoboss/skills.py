"""The skills: each one looks at a coin's 15-minute candles and says "buy here" or nothing.

Long only (we only buy, never bet on a fall). Every skill uses only candles that already finished.
"""
import math

import pandas as pd

from . import config as C


def money(x):
    if x >= 1:
        return f"${x:,.2f}"
    return f"${x:.{max(2, 3 - math.floor(math.log10(x)))}f}"


def _sig(x):
    return float(f"{x:.6g}")


def prepare(df):
    """Adds the helper lines every skill uses."""
    df = df.copy()
    c = df["Close"]
    df["EMA20"] = c.ewm(span=20, adjust=False).mean()
    df["EMA50"] = c.ewm(span=50, adjust=False).mean()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(), (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    df["RSI"] = 100 - 100 / (1 + up / dn.replace(0, float("nan")))
    df["VolAvg20"] = df["Volume"].shift().rolling(20).mean()
    df["High8"] = df["High"].rolling(8).max()                       # highest point of the last 2 hours
    df["Wild"] = ((df["High"] - df["Low"]) / c).rolling(96).mean() * 100   # avg candle size over 24h, in %
    df["DollarVol24h"] = (c * df["Volume"]).rolling(96).sum()
    return df


def row_at(df, t):
    """Index of the last candle that finished by time t (or -1)."""
    return int(df.index.searchsorted(t - pd.Timedelta(C.CANDLE), side="right")) - 1


def wildest(frames, t, n=None):
    """The n coins moving the most right now (and that people actually trade)."""
    n = n or C.WATCH_COUNT
    scores = {}
    for coin, df in frames.items():
        if coin == C.MARKET_COIN:
            continue
        i = row_at(df, t)
        if i < 96:
            continue
        r = df.iloc[i]
        if r["DollarVol24h"] >= C.MIN_24H_DOLLAR_VOL and r["Wild"] == r["Wild"]:
            scores[coin] = r["Wild"]
    return sorted(scores, key=scores.get, reverse=True)[:n]


def weather(frames, t):
    df = frames.get(C.MARKET_COIN)
    if df is None:
        return "cloudy", "Bitcoin data missing - assuming cloudy"
    i = row_at(df, t)
    if i < 16:
        return "cloudy", "Not enough Bitcoin data - assuming cloudy"
    chg = (df["Close"].iloc[i] / df["Close"].iloc[i - 16] - 1) * 100
    w = "stormy" if chg <= C.STORM_DROP_PCT else "sunny" if chg >= 0 else "cloudy"
    return w, f"Bitcoin {chg:+.1f}% in the last 4 hours"


# ---------------------------------------------------------------- the skills

def breakout_rocket(df, i):
    """A loud green candle pushing on the 2-hour high, in an uptrend. Buy if it breaks the high."""
    if i < 60:
        return None
    r = df.iloc[i]
    if not (r["Close"] > r["EMA50"] and r["Close"] > r["Open"] and r["VolAvg20"] > 0
            and r["Volume"] >= 1.5 * r["VolAvg20"] and r["Close"] >= r["High8"] * 0.99):
        return None
    entry = r["High8"] * 1.001
    return {"order_type": "buy_stop", "entry": entry, "stop": entry - 1.5 * r["ATR"],
            "reason": f"Loud green candle ({r['Volume'] / r['VolAvg20']:.1f}x volume) pushing on its 2-hour high"}


def dip_catcher(df, i):
    """Uptrend, price dipped to its 20-candle average line and bounced. Buy if it keeps going up."""
    if i < 60:
        return None
    r = df.iloc[i]
    if not (r["EMA20"] > r["EMA50"] and r["Close"] > r["EMA20"] and r["Low"] <= r["EMA20"] * 1.002
            and r["Close"] > r["Open"] and 40 <= r["RSI"] <= 60):
        return None
    entry = r["High"] * 1.001
    return {"order_type": "buy_stop", "entry": entry, "stop": float(df["Low"].iloc[i - 2:i + 1].min()) * 0.998,
            "reason": f"Uptrend dipped to its average line and bounced (RSI {r['RSI']:.0f})"}


SKILLS = {"Breakout Rocket": breakout_rocket, "Dip Catcher": dip_catcher}

KID_EXPLAINERS = {
    "Breakout Rocket": "The coin is going up and lots of people just jumped in. If it breaks above "
                       "its top from the last 2 hours, we hop on the rocket.",
    "Dip Catcher": "The coin is going up overall, took a little rest, and is bouncing again. "
                   "We buy when the bounce keeps going.",
}


def make_signal(coin, skill, idea):
    entry = _sig(idea["entry"])
    # too-tight stops get widened to MIN_RISK_PCT, so the target is big enough to beat the spread
    stop = _sig(min(idea["stop"], entry * (1 - C.MIN_RISK_PCT / 100)))
    risk = entry - stop
    if risk <= 0 or not (C.MIN_RISK_PCT <= risk / entry * 100 <= C.MAX_RISK_PCT):
        return None
    return {"coin": coin, "skill": skill, "order_type": idea["order_type"], "entry": entry, "stop": stop,
            "target": entry + C.TARGET_R * risk, "risk_pct": round(risk / entry * 100, 2),
            "reason": idea["reason"]}


def find_new(frames, t, blocked):
    """New signals at time t among the wildest coins. blocked = coins we must skip right now."""
    w, note = weather(frames, t)
    out = []
    if w == "stormy":
        return out, w, note
    for coin in wildest(frames, t):
        if coin in blocked:
            continue
        df = frames[coin]
        i = row_at(df, t)
        for name, fn in SKILLS.items():
            idea = fn(df, i)
            if idea and (s := make_signal(coin, name, idea)):
                out.append(s)
                break
        if len(out) >= C.MAX_NEW_PER_RUN:
            break
    return out, w, note
