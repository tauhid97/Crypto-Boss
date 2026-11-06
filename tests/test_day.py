"""Offline tests for the day skill Wake-Up Rally (no internet needed): python -m tests.test_day"""
import numpy as np
import pandas as pd

from cryptoboss import config as C

T = pd.Timestamp("2026-11-04 10:00", tz="UTC")       # 10 AM UTC: 40 finished candles today


def daily_down(days=80, start=100.0, end=70.0, vol=1000.0):
    idx = pd.date_range(T.floor("1D") - pd.Timedelta(days=days), periods=days, freq="1D", tz="UTC")
    c = np.linspace(start, end, days)
    return pd.DataFrame({"Open": c * 1.005, "High": c * 1.02, "Low": c * 0.98, "Close": c,
                         "Volume": vol}, index=idx)


def intraday(prev_close, jump=0.06, vol_per_candle=50.0):
    """3 days of 15m candles: flat at prev_close, then today climbing jump% by 10 AM on heavy volume."""
    idx = pd.date_range(T.floor("1D") - pd.Timedelta(days=3), T - pd.Timedelta("15min"), freq="15min", tz="UTC")
    today = idx >= T.floor("1D")
    n = today.sum()
    close = np.where(today, 0, prev_close).astype(float)
    close[today] = prev_close * (1 + jump * np.arange(1, n + 1) / n)
    opn = np.r_[prev_close, close[:-1]]
    vol = np.where(today, vol_per_candle, 10.0) * 1e5
    return pd.DataFrame({"Open": opn, "High": np.maximum(opn, close) * 1.001, "Low": np.minimum(opn, close) * 0.999,
                         "Close": close, "Volume": vol}, index=idx)


def frames_for(coins):
    from cryptoboss.skills import prepare
    out = {c: prepare(df) for c, df in coins.items()}
    btc = intraday(70000.0, jump=0.0)
    out["BTC"] = prepare(btc)
    return out


def test_fires():
    from cryptoboss.skills import day_context, find_day, wake_up_rally
    d = daily_down()
    df = intraday(70.0)
    x = day_context(df, d, T)
    assert x["day_chg"] > 0.05 and x["drop60"] < -0.15 and x["below50"] and x["rvol"] > 2, x
    assert wake_up_rally(x) is not None
    sigs = find_day(frames_for({"AAA": df}), lambda c: d, T, set(), set())
    assert [x["skill"] for x in sigs] == ["Wake-Up Rally", "Wake-Up Rally (Dip)"], sigs
    dip = sigs[1]                                              # dip twin: waits for a drop, buys cheaper
    assert dip["order_type"] == "dip_bounce" and dip["stop"] < dip["entry"] < sigs[0]["entry"], dip
    s = sigs[0]
    assert s["skill"] == "Wake-Up Rally" and s["max_hold"] == "24h" and s["entry_window"] == "4h", s
    assert s["entry"] > s["stop"] and s["target"] > s["entry"], s
    # already fired today -> skip; coin busy -> skip
    assert find_day(frames_for({"AAA": df}), lambda c: d, T, set(), {("AAA", "Wake-Up Rally"), ("AAA", "Wake-Up Rally (Dip)")}) == []
    assert find_day(frames_for({"AAA": df}), lambda c: d, T, {"AAA"}, set()) == []
    print("fires OK")


def test_does_not_fire():
    from cryptoboss.skills import day_context, find_day, wake_up_rally
    up = daily_down(start=50.0, end=70.0)                      # it was rising, not falling
    assert wake_up_rally(day_context(intraday(70.0), up, T)) is None
    small = intraday(70.0, jump=0.02)                          # only up 2% today
    calls = []
    assert find_day(frames_for({"AAA": small}), lambda c: calls.append(c) or daily_down(), T, set(), set()) == []
    assert calls == [], "should not even download daily candles for a coin up less than 3%"
    busy_days = daily_down(vol=1e9)                            # today's volume is only normal for this coin
    assert day_context(intraday(70.0), busy_days, T)["rvol"] < 2
    assert wake_up_rally(day_context(intraday(70.0), busy_days, T)) is None
    # stormy Bitcoin -> no new buys
    f = frames_for({"AAA": intraday(70.0)})
    from cryptoboss.skills import prepare
    btc = intraday(70000.0, jump=0.0)
    btc.iloc[-16:, btc.columns.get_loc("Close")] = np.linspace(70000, 67000, 16)
    f["BTC"] = prepare(btc)
    assert find_day(f, lambda c: daily_down(), T, set(), set()) == []
    print("does not fire OK")


def test_holds_a_day():
    from cryptoboss.tracker import settle
    from cryptoboss.bot import signal_text
    t0 = pd.Timestamp("2026-11-01 12:00", tz="UTC")
    idx = pd.date_range(t0, periods=40, freq="15min", tz="UTC")
    b = pd.DataFrame({"Open": 10.0, "High": 10.1, "Low": 9.95, "Close": 10.05, "Volume": 1.0}, index=idx)
    sig = {"published_at": t0.isoformat(), "order_type": "buy_stop", "entry": 10.0, "stop": 9.8, "target": 10.4,
           "status": "pending", "entry_window": "4h", "max_hold": "24h"}
    r = settle(dict(sig), b, t0 + pd.Timedelta(hours=10))
    assert r["status"] == "open", r                            # a scalp would have been sold at 4 hours
    old = dict(sig, entry_window=float("nan"), max_hold=float("nan"))   # old rows from the CSV: normal 4h
    assert settle(dict(old), b, t0 + pd.Timedelta(hours=10))["status"] == "timeout"
    text = signal_text(dict(sig, coin="AAA", skill="Wake-Up Rally", risk_pct=2.0, reason="test"), "sunny")
    assert "Sell after 24 hours" in text and "Wake-Up Rally" in text, text
    text2 = signal_text({k: v for k, v in sig.items() if k not in ("entry_window", "max_hold")}
                        | {"coin": "AAA", "skill": "Dip Catcher", "risk_pct": 2.0, "reason": "t"}, "sunny")
    assert "Sell after 4 hours" in text2, text2
    print("holds a day OK")


if __name__ == "__main__":
    test_fires()
    test_does_not_fire()
    test_holds_a_day()
    print("ALL OK")
