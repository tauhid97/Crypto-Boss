"""Offline tests with made-up prices (no internet needed): python -m tests.test_bot"""
import os
import shutil

import numpy as np
import pandas as pd

from cryptoboss import config as C

rng = np.random.default_rng(3)
TMP = "/tmp/cryptoboss_test"


def bars(start, rows):
    """rows = list of (open, high, low, close) -> 15-minute candles."""
    idx = pd.date_range(start, periods=len(rows), freq="15min", tz="UTC")
    df = pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx)
    df["Volume"] = 1_000_000.0
    return df


def walk(start, n, px, drift=0.0, noise=0.004, vol=1_000_000.0):
    idx = pd.date_range(start, periods=n, freq="15min", tz="UTC")
    close = px * np.exp(np.cumsum(rng.normal(drift, noise, n)))
    opn = np.r_[px, close[:-1]]
    high = np.maximum(opn, close) * (1 + abs(rng.normal(0, noise / 2, n)))
    low = np.minimum(opn, close) * (1 - abs(rng.normal(0, noise / 2, n)))
    return pd.DataFrame({"Open": opn, "High": high, "Low": low, "Close": close,
                         "Volume": vol * rng.uniform(0.7, 1.3, n)}, index=idx)


def test_settle():
    from cryptoboss.tracker import settle
    t0 = pd.Timestamp("2026-11-01 12:00", tz="UTC")
    sig = {"published_at": t0.isoformat(), "order_type": "buy_stop", "entry": 10.0, "stop": 9.8,
           "target": 10.4, "status": "pending"}
    # fills on bar 2, target on bar 3
    b = bars(t0, [(9.9, 9.95, 9.85, 9.9), (9.95, 10.1, 9.9, 10.05), (10.1, 10.5, 10.05, 10.4)])
    r = settle(dict(sig), b, t0 + pd.Timedelta(hours=1))
    assert r["status"] == "target" and r["fill_price"] == 10.0, r
    # spread makes it a bit less than +2R
    assert 1.5 < r["r_multiple"] < 2.0, r
    # stop and fill in the same bar -> counted as a loss
    b2 = bars(t0, [(9.9, 10.1, 9.7, 9.8)])
    r2 = settle(dict(sig), b2, t0 + pd.Timedelta(hours=1))
    assert r2["status"] == "stop" and r2["r_multiple"] < -1.0, r2
    # never reaches entry within the entry window -> no trade
    b3 = bars(t0, [(9.9, 9.95, 9.85, 9.9)] * 8)
    r3 = settle(dict(sig), b3, t0 + pd.Timedelta(hours=2))
    assert r3["status"] == "no_fill" and r3["r_multiple"] == 0, r3
    # still waiting (window not over) -> stays pending
    r4 = settle(dict(sig), b3.iloc[:2], t0 + pd.Timedelta(minutes=30))
    assert r4["status"] == "pending", r4
    # filled, then drifts sideways past the max hold -> sold on time
    b5 = bars(t0, [(9.95, 10.05, 9.9, 10.0)] + [(10.0, 10.1, 9.95, 10.05)] * 20)
    r5 = settle(dict(sig), b5, t0 + pd.Timedelta(hours=6))
    assert r5["status"] == "timeout", r5
    # filled, still open (no exit yet)
    r6 = settle(dict(sig), b5.iloc[:3], t0 + pd.Timedelta(minutes=45))
    assert r6["status"] == "open" and r6["fill_price"] == 10.0, r6
    # an open signal keeps settling on later runs
    r7 = settle(dict(r6), b5, t0 + pd.Timedelta(hours=6))
    assert r7["status"] == "timeout" and r7["fill_price"] == 10.0, r7
    print("settle OK")


def test_skills():
    from cryptoboss import skills
    t0 = pd.Timestamp("2026-10-30 00:00", tz="UTC")
    calm = walk(t0, 200, 100, noise=0.001)
    wild = walk(t0, 200, 1.0, noise=0.02)
    thin = walk(t0, 200, 1.0, noise=0.03, vol=10.0)          # wild but nobody trades it
    f = {k: skills.prepare(v) for k, v in {"CALM": calm, "WILD": wild, "THIN": thin}.items()}
    top = skills.wildest(f, t0 + pd.Timedelta(minutes=15 * 200), 2)
    assert top[0] == "WILD" and "THIN" not in top, top
    # rocket: steady climb, then a loud green candle near the 2-hour high
    up = walk(t0, 199, 50, drift=0.001, noise=0.002)
    last = up["Close"].iloc[-1]
    loud = pd.DataFrame({"Open": [last], "High": [last * 1.012], "Low": [last * 0.999], "Close": [last * 1.011],
                         "Volume": [6_000_000.0]}, index=[up.index[-1] + pd.Timedelta(minutes=15)])
    df = skills.prepare(pd.concat([up, loud]))
    s = skills.breakout_rocket(df, len(df) - 1)
    assert s and s["entry"] > df["Close"].iloc[-1] > s["stop"], s
    sig = skills.make_signal("ROCK", "Breakout Rocket", s)
    assert sig and abs((sig["target"] - sig["entry"]) - C.TARGET_R * (sig["entry"] - sig["stop"])) < 1e-9
    assert C.MIN_RISK_PCT <= sig["risk_pct"] <= C.MAX_RISK_PCT
    # tiny coins keep their tiny prices
    assert skills.money(0.0000049) == "$0.000004900" and skills.money(77784.5) == "$77,784.50"
    print("skills OK")


def setup_tmp():
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    for k in ["SIGNALS_FILE", "STATE_FILE", "REPORT_FILE"]:
        setattr(C, k, os.path.join(TMP, os.path.basename(getattr(C, k))))


def fake_market(days=4):
    t0 = pd.Timestamp("2026-10-28 00:00", tz="UTC")
    n = days * 96
    m = {"BTC": walk(t0, n, 78000, drift=0.0002, noise=0.003, vol=300),
         "SOL": walk(t0, n, 94, drift=0.0004, noise=0.009, vol=40_000),
         "PEPE": walk(t0, n, 0.0000049, drift=0.0005, noise=0.015, vol=3e11),
         "DOGE": walk(t0, n, 0.075, drift=0.0003, noise=0.012, vol=4e7),
         "LTC": walk(t0, n, 55, noise=0.002, vol=20_000)}
    for k, df in m.items():                                   # give everyone some loud breakout candles
        for i in range(120, n, 37):
            df.iloc[i, df.columns.get_loc("Volume")] *= 5
            df.iloc[i, df.columns.get_loc("High")] = df["High"].iloc[i] * 1.01
            df.iloc[i, df.columns.get_loc("Close")] = max(df["Close"].iloc[i], df["High"].iloc[i - 8:i].max())
    return m


def test_live():
    from cryptoboss import bot, data, notify
    setup_tmp()
    market = fake_market()
    sent = []
    notify.send = lambda t: sent.append(t) or True
    bot.load_coins = lambda: list(market)
    calls = []
    bot.daily = lambda c: calls.append(c)        # offline: no daily candles (day skills stay quiet)
    end = market["BTC"].index[-1] + pd.Timedelta(minutes=15)
    t = market["BTC"].index[0] + pd.Timedelta(hours=40)
    runs = 0
    while t <= end:
        bot.get_all = (lambda now: (lambda coins, now_=None: data.closed({c: market[c] for c in coins}, now)))(t)
        bot.run(now=t)
        runs += 1
        t += pd.Timedelta(minutes=15)
    sig = bot.load_signals()
    print(sig[["published_at", "coin", "skill", "entry", "stop", "status", "r_multiple"]].tail(15).to_string())
    assert len(sig), "no signals at all"
    assert set(sig["status"]) - {"pending", "open"}, "nothing ever finished"
    # each skill: never two signals on one coin within the cooldown
    for (c, k), g in sig.groupby(["coin", "skill"]):
        times = pd.to_datetime(g["published_at"]).sort_values()
        assert (times.diff().dropna() >= pd.Timedelta(C.COOLDOWN)).all(), (c, k, times)
    # daily caps: 3 per skill, 30 in total (UTC days)
    day = pd.to_datetime(sig["published_at"], utc=True).dt.floor("1D")
    assert sig.groupby([day, sig["skill"]]).size().max() <= C.SKILL_DAILY_CAP, sig.groupby([day, sig["skill"]]).size()
    assert sig.groupby(day).size().max() <= C.DAILY_CAP
    # more practice than before: some coin was traded by 2+ skills at once
    print("signals:", len(sig), "| skills sharing a coin at once:",
          sig.groupby(["coin", "published_at"]).size().max())
    new = [s for s in sent if "CRYPTO BOSS" in s and ("Buy" in s or "short form" in s)]
    res = [s for s in sent if "] - results" in s]
    recaps = [s for s in sent if "recap" in s.lower()]
    assert new and res and 1 <= len(recaps) <= 3, (len(new), len(res), len(recaps))
    assert all("PRACTICE" in s for s in new)
    assert os.path.exists(C.REPORT_FILE) and "Crypto Boss" in open(C.REPORT_FILE).read()
    # a run with no data tells Boss once a day, not every 15 minutes
    sent.clear()
    bot.get_all = lambda coins, now_=None: {}
    bot.run(now=end); bot.run(now=end + pd.Timedelta(minutes=15))
    assert len(sent) == 1, sent
    print("\n--- sample signal ---\n" + new[0])
    shorts = [s for s in sent if "short form" in s]
    if shorts:
        print("\n--- sample short form ---\n" + shorts[0])
    print("\n--- sample result ---\n" + res[0])
    print("\n--- sample recap ---\n" + recaps[0])
    print("live OK")


def test_backtest():
    from cryptoboss import backtest
    market = fake_market(6)
    trades, text = backtest.run(market, days=4)
    print(text)
    assert len(trades) and "trades" in text
    print("backtest OK")


if __name__ == "__main__":
    test_settle()
    test_skills()
    test_live()
    test_backtest()
    print("ALL OK")
