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
    # extra lines for the YouTube skills
    df["EMA9"] = c.ewm(span=9, adjust=False).mean()
    df["EMA21"] = c.ewm(span=21, adjust=False).mean()
    df["EMA200"] = c.ewm(span=200, adjust=False).mean()
    df["MACD"] = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["MACDSig"] = df["MACD"].ewm(span=9, adjust=False).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    df["BBMid"], df["BBLow"] = mid, mid - 2 * sd
    typ = (df["High"] + df["Low"] + c) / 3
    df["VWAP"] = (typ * df["Volume"]).rolling(96).sum() / df["Volume"].rolling(96).sum()   # 24-hour VWAP
    lo14, hi14 = df["Low"].rolling(14).min(), df["High"].rolling(14).max()
    df["StochK"] = (100 * (c - lo14) / (hi14 - lo14).replace(0, float("nan"))).rolling(3).mean()
    df["StochD"] = df["StochK"].rolling(3).mean()
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


# --- YouTube skills: the most-shared free scalping setups, written down exactly so they can be graded ---

def _swing_low(df, i, n=5):
    return float(df["Low"].iloc[i - n + 1:i + 1].min()) * 0.998


def ema_cross(df, i):
    """9/21 EMA crossover, only above the 200 EMA (the classic "9 and 21" YouTube setup)."""
    if i < 210:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    if not (p["EMA9"] <= p["EMA21"] and r["EMA9"] > r["EMA21"] and r["Close"] > r["EMA200"]):
        return None
    return {"order_type": "buy_stop", "entry": r["High"] * 1.001, "stop": _swing_low(df, i),
            "reason": "Fast line (9) crossed above slow line (21), and price is above the 200 line"}


def macd_200(df, i):
    """MACD crosses up while below zero, price above the 200 EMA (the famous "MACD + 200 EMA" video)."""
    if i < 210:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    if not (p["MACD"] <= p["MACDSig"] and r["MACD"] > r["MACDSig"] and r["MACD"] < 0
            and r["Close"] > r["EMA200"]):
        return None
    return {"order_type": "buy_stop", "entry": r["High"] * 1.001, "stop": _swing_low(df, i), "target_r": 1.5,
            "reason": "MACD turned up from below zero while the coin is above its 200 line"}


def band_bounce(df, i):
    """Price fell below the lower Bollinger Band with RSI under 30, then a green candle (mean reversion).
    Target: back to the middle band."""
    if i < 30:
        return None
    r, p = df.iloc[i], df.iloc[i - 1]
    if not (p["Close"] < p["BBLow"] and p["RSI"] < 30 and r["Close"] > r["Open"]):
        return None
    entry = r["High"] * 1.001
    return {"order_type": "buy_stop", "entry": entry, "stop": _swing_low(df, i, 3), "target": r["BBMid"],
            "reason": f"Stretched too far down (RSI {p['RSI']:.0f}) and starting to snap back"}


def vwap_pullback(df, i):
    """Above VWAP and trending, dips to touch VWAP and closes back above it."""
    if i < 100:
        return None
    r = df.iloc[i]
    if not (r["EMA21"] > r["VWAP"] and r["Low"] <= r["VWAP"] * 1.002 and r["Close"] > r["VWAP"]
            and r["Close"] > r["Open"] and r["RSI"] > 50):
        return None
    return {"order_type": "buy_stop", "entry": r["High"] * 1.001, "stop": _swing_low(df, i, 3),
            "reason": "Dipped to the day's average price (VWAP) and bounced"}


def triple_check(df, i):
    """Stochastic crosses up from under 20, RSI over 50, MACD above its signal (the "Stoch + RSI + MACD" video)."""
    if i < 40:
        return None
    r = df.iloc[i]
    k = df["StochK"].iloc[i - 4:i + 1]
    if not ((k < 20).any() and r["StochK"] > r["StochD"] and r["RSI"] > 50 and r["MACD"] > r["MACDSig"]):
        return None
    return {"order_type": "buy_stop", "entry": r["High"] * 1.001, "stop": _swing_low(df, i), "target_r": 1.5,
            "reason": "Stochastic bounced from oversold, RSI and MACD both agree"}


# --- day skills: borrowed from Boss's stock bot, they look at whole days and may hold up to 1 day ---

def day_context(df, daily, t):
    """What a day skill needs at time t: the finished days before today + today's 15-minute candles so far."""
    today = t.floor("1D")
    d = daily[daily.index < today]
    b = df[(df.index >= today) & (df.index + pd.Timedelta(C.CANDLE) <= t)]
    if len(d) < 60 or not len(b):
        return None
    c, h, lo = d["Close"], d["High"], d["Low"]
    tr = pd.concat([h - lo, (h - c.shift()).abs(), (lo - c.shift()).abs()], axis=1).max(axis=1)
    typ = (b["High"] + b["Low"] + b["Close"]) / 3
    vol20 = float(d["Volume"].iloc[-20:].mean())
    day_vol = float(b["Volume"].sum())
    return {"last": float(b["Close"].iloc[-1]), "hod": float(b["High"].max()), "lod": float(b["Low"].min()),
            "vwap": float((typ * b["Volume"]).sum() / day_vol) if day_vol > 0 else float(b["Close"].iloc[-1]),
            "rvol": day_vol / (vol20 * len(b) / 96) if vol20 > 0 else 0.0,
            "day_chg": float(b["Close"].iloc[-1]) / float(c.iloc[-1]) - 1,
            "drop60": float(c.iloc[-1]) / float(c.iloc[-60]) - 1,
            "below50": float(c.iloc[-1]) < float(c.iloc[-50:].mean()),
            "atr": float(tr.ewm(alpha=1 / 14, adjust=False).mean().iloc[-1])}


def wake_up_rally(x):
    """Stock bot's Downtrend Reversal: down 15%+ in 60 days and under its 50-day line, then today it jumps
    3%+ on 2x the usual volume with a big range. Buy as it breaks its high of the day.
    Crypto test (Aug 2025 - Nov 2026, 1h candles, fee on): 76 trades, +0.45R each, held up to 1 day."""
    if x["rvol"] < 2.0 or x["day_chg"] * 100 < 3.0 or x["drop60"] * 100 > -15 or not x["below50"]:
        return None
    if (x["hod"] - x["lod"]) < x["atr"] or x["last"] < x["vwap"] or (x["hod"] / x["last"] - 1) * 100 > 1.0:
        return None
    entry = x["hod"] * 1.001
    return {"order_type": "buy_stop", "entry": entry, "stop": max(x["vwap"] * 0.999, entry - 0.8 * x["atr"]),
            "reason": f"Down {abs(x['drop60']) * 100:.0f}% in 60 days, now up {x['day_chg'] * 100:.1f}% today "
                      f"on {x['rvol']:.1f}x volume - buy if it makes a new high"}


DAY_SKILLS = {"Wake-Up Rally": wake_up_rally}


def find_day(frames, get_daily, t, blocked, skip):
    """Day skills look at EVERY coin people trade (not just the 5 wildest).
    skip = (coin, skill) pairs that already fired today. get_daily(coin) downloads that coin's daily candles."""
    w, _ = weather(frames, t)
    out = []
    if w == "stormy":
        return out
    for coin, df in frames.items():
        if coin == C.MARKET_COIN or coin in blocked:
            continue
        i = row_at(df, t)
        if i < 96 or not df["DollarVol24h"].iloc[i] >= C.MIN_24H_DOLLAR_VOL:
            continue
        # quick check first, so we only download daily candles for coins that are up a lot today
        before = df[df.index < t.floor("1D")]
        if not len(before) or df["Close"].iloc[i] / before["Close"].iloc[-1] - 1 < 0.03:
            continue
        daily = get_daily(coin)
        x = day_context(df, daily, t) if daily is not None else None
        if x is None:
            continue
        for name, fn in DAY_SKILLS.items():
            if (coin, name) in skip:
                continue
            idea = fn(x)
            if idea and (s := make_signal(coin, name, idea)):
                s.update(entry_window=C.DAY_ENTRY_WINDOW, max_hold=C.DAY_MAX_HOLD)
                out.append(s)
        if len(out) >= C.MAX_NEW_PER_RUN:
            break
    return out


# --- dip twins: the same setups, but we wait for a small drop, then buy only after a green bounce candle ---

def dip_twin(fn):
    """Same setup as fn, but wait for a dip a little under the last price, then buy on a green bounce candle."""
    def twin(df, i):
        idea = fn(df, i)
        if not idea:
            return None
        r = df.iloc[i]
        entry = r["Close"] - C.DIP_ATR * r["ATR"]
        return dict(idea, order_type="dip_bounce", entry=entry, stop=min(idea["stop"], entry - r["ATR"]),
                    reason=idea["reason"] + " - dip version: buy only after it dips, then bounces back up")
    twin.__doc__ = f"Dip twin of {fn.__name__}."
    return twin


def wake_up_rally_dip(x):
    """Dip twin of Wake-Up Rally: same coin and day, but buy halfway back down to today's average price."""
    idea = wake_up_rally(x)
    if not idea:
        return None
    entry = (x["last"] + x["vwap"]) / 2
    return dict(idea, order_type="dip_bounce", entry=entry, stop=min(x["vwap"] * 0.99, entry - 0.5 * x["atr"]),
                reason=idea["reason"].replace("buy if it makes a new high", "buy only after it dips halfway back, then bounces up"))


DAY_SKILLS["Wake-Up Rally (Dip)"] = wake_up_rally_dip

BASE_SKILLS = {"Breakout Rocket": breakout_rocket, "Dip Catcher": dip_catcher, "EMA Cross": ema_cross,
               "MACD 200": macd_200, "Band Bounce": band_bounce, "VWAP Pullback": vwap_pullback,
               "Triple Check": triple_check}
SKILLS = {**BASE_SKILLS, **{f"{k} (Dip)": dip_twin(f) for k, f in BASE_SKILLS.items()}}
ALL_SKILLS = {**SKILLS, **DAY_SKILLS}

KID_EXPLAINERS = {
    "Breakout Rocket": "The coin is going up and lots of people just jumped in. If it breaks above "
                       "its top from the last 2 hours, we hop on the rocket.",
    "Dip Catcher": "The coin is going up overall, took a little rest, and is bouncing again. "
                   "We buy when the bounce keeps going.",
    "EMA Cross": "A fast-moving average line just crossed above a slower one, and the big-picture line "
                 "says the coin is in an uptrend. We buy when it keeps rising.",
    "MACD 200": "The coin is in an uptrend, had a small dip, and its momentum just turned back up.",
    "Band Bounce": "The coin dropped too far, too fast, like a stretched rubber band. We buy the snap back "
                   "and sell at the middle.",
    "VWAP Pullback": "The coin came back to the average price everyone paid today and bounced off it.",
    "Triple Check": "Three different gauges all agree the coin is turning up from a dip.",
    "Wake-Up Rally": "This coin has been sliding down for months. Today it suddenly woke up and is jumping "
                     "on lots of buying. If it keeps climbing to a new high, we buy, and may hold up to 1 day.",
}
DIP_WORDS = " Dip version: we wait for a small drop, then buy only once a candle closes green back above the dip price (proof it is bouncing up, not still falling)."
KID_EXPLAINERS.update({f"{k} (Dip)": v + DIP_WORDS for k, v in list(KID_EXPLAINERS.items())})


def make_signal(coin, skill, idea):
    entry = _sig(idea["entry"])
    # too-tight stops get widened to MIN_RISK_PCT, so the target is big enough to beat the spread
    stop = _sig(min(idea["stop"], entry * (1 - C.MIN_RISK_PCT / 100)))
    risk = entry - stop
    if risk <= 0 or not (C.MIN_RISK_PCT <= risk / entry * 100 <= C.MAX_RISK_PCT):
        return None
    target = _sig(idea["target"]) if idea.get("target") else entry + idea.get("target_r", C.TARGET_R) * risk
    if target < entry * (1 + C.MIN_TARGET_PCT / 100):    # too small a win to beat the spread
        return None
    return {"coin": coin, "skill": skill, "order_type": idea["order_type"], "entry": entry, "stop": stop,
            "target": target, "risk_pct": round(risk / entry * 100, 2),
            "reason": idea["reason"]}


def find_new(frames, t, blocked, left=None, room=None):
    """New signals at time t among the wildest coins. blocked = coins, or (coin, skill) pairs, to skip right now.
    Without left/room (the backtest): first skill that fires takes the coin. With them (the live bot): every skill
    may take the coin; left = {skill: new trades it may still make today}, room = total still allowed today."""
    w, note = weather(frames, t)
    out = []
    if w == "stormy":
        return out, w, note
    many = left is not None
    cap = C.MAX_NEW_PER_RUN if room is None else min(C.MAX_NEW_PER_RUN, room)
    for coin in wildest(frames, t):
        if coin in blocked:
            continue
        df = frames[coin]
        i = row_at(df, t)
        for name, fn in SKILLS.items():
            if len(out) >= cap:
                return out, w, note
            if many and ((coin, name) in blocked or left.get(name, C.SKILL_DAILY_CAP) <= 0):
                continue
            idea = fn(df, i)
            if idea and (s := make_signal(coin, name, idea)):
                out.append(s)
                if not many:
                    break
                left[name] = left.get(name, C.SKILL_DAILY_CAP) - 1
        if len(out) >= cap:
            break
    return out, w, note
