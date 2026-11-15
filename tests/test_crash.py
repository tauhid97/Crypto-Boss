"""Offline tests for Crash Dip (no internet needed): python -m tests.test_crash"""
import numpy as np
import pandas as pd

from cryptoboss import config as C

T0 = pd.Timestamp("2026-11-01 00:00", tz="UTC")


def candles(closes, vol=1e6):
    idx = pd.date_range(T0, periods=len(closes), freq="15min", tz="UTC")
    c = np.asarray(closes, dtype=float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c) * 1.002, "Low": np.minimum(o, c) * 0.998,
                         "Close": c, "Volume": vol}, index=idx)


def crash_frames():
    from cryptoboss.skills import prepare
    flat = [100 + (i % 2) * 0.3 for i in range(200)]
    crash = flat + list(np.linspace(100, 90, 9))           # falls 10% in about 2 hours
    return {"AAA": prepare(candles(crash)), "BBB": prepare(candles(flat + [100.0] * 9))}


def test_fires_on_a_crash_only():
    from cryptoboss.skills import find_crash
    f = crash_frames()
    t = f["AAA"].index[-1] + pd.Timedelta("15min")
    sigs = find_crash(f, t, set(), 5)
    assert [s["coin"] for s in sigs] == ["AAA"], sigs
    s = sigs[0]
    assert s["skill"] == "Crash Dip" and s["order_type"] == "buy_now" and s["exit_rule"] == "cool_down", s
    assert abs(s["stop"] / s["entry"] - 0.90) < 1e-6 and s["max_hold"] == "14D", s
    assert find_crash(f, t, {("AAA", "Crash Dip")}, 5) == []        # already trading it / cooldown
    assert find_crash(f, t, set(), 0) == []                         # no room left today
    print("fires on a crash only OK")


def test_ignores_stormy_weather():
    from cryptoboss.skills import find_crash, prepare
    f = crash_frames()
    f["BTC"] = prepare(candles([70000.0] * 200 + list(np.linspace(70000, 65000, 9))))
    t = f["AAA"].index[-1] + pd.Timedelta("15min")
    assert "AAA" in [s["coin"] for s in find_crash(f, t, set(), 5)]
    print("ignores stormy weather OK")


def sig_for(entry=90.0):
    return {"published_at": T0.isoformat(), "order_type": "buy_now", "entry": entry, "stop": entry * 0.9,
            "target": entry * 1.2, "status": "pending", "entry_window": "30min", "max_hold": "14D",
            "exit_rule": "cool_down"}


def test_buys_now_and_sells_when_cooled():
    from cryptoboss.tracker import settle
    idx = pd.date_range(T0, periods=6, freq="15min", tz="UTC")
    b = pd.DataFrame({"Open": [90.5, 91, 92, 93, 93.5, 94], "High": [91, 92, 93, 94, 94, 95],
                      "Low": [90, 90.5, 91.5, 92.5, 93, 93.5], "Close": [91, 92, 93, 93.5, 94, 94.5],
                      "Volume": 1.0, "RSI": [40, 45, 50, 25, 50, 50], "EMA200": 100.0}, index=idx)
    r = settle(sig_for(), b, idx[-1] + pd.Timedelta("15min"))
    assert r["fill_price"] == 90.5, r                               # bought at the first candle's open
    # candle 3: profit about +2.7% after the spread and RSI 25 < 32 -> sell at candle 4's open
    assert r["status"] == "target" and r["exit_price"] == 93.5 and r["exit_time"] == idx[4].isoformat(), r
    assert r["pct_return"] > 2 and 0 < r["r_multiple"] < 1, r       # R measured from the real buy price
    print("buys now and sells when cooled OK")


def test_holds_while_losing_then_stops():
    from cryptoboss.tracker import settle
    idx = pd.date_range(T0, periods=4, freq="15min", tz="UTC")
    b = pd.DataFrame({"Open": [90.0, 88, 85, 82], "High": [90.5, 88.5, 85.5, 82.5], "Low": [87.5, 84.5, 81.5, 79],
                      "Close": [88, 85, 82, 80], "Volume": 1.0, "RSI": 5.0, "EMA200": 100.0}, index=idx)
    r = settle(sig_for(), b, idx[2] + pd.Timedelta("15min"))
    assert r["status"] == "open", r                                 # low RSI but no profit -> keep holding
    r = settle(sig_for(), b, idx[-1] + pd.Timedelta("15min"))
    assert r["status"] == "stop" and r["exit_price"] == 81.0, r     # -10% safety price
    print("holds while losing, then stops OK")


def test_messages():
    from cryptoboss.bot import short_text, signal_text
    s = dict(sig_for(), coin="AAA", skill="Crash Dip", risk_pct=10.0, reason="Crashed 10% under its average")
    text = signal_text(s, "Bitcoin -3% in 4 hours")
    assert "1. Buy now, at about $90.00" in text and "calms down" in text and "14 days" in text, text
    assert "NostalgiaForInfinity" in text, text
    assert "win when it bounces and calms down" in short_text([s, s]) and "max 14 days" in short_text([s, s])
    print("messages OK")


if __name__ == "__main__":
    test_fires_on_a_crash_only()
    test_ignores_stormy_weather()
    test_buys_now_and_sells_when_cooled()
    test_holds_while_losing_then_stops()
    test_messages()
    print("ALL OK")
