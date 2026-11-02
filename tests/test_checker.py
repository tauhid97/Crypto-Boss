"""Offline tests for the Signal Checker (no internet needed): python -m tests.test_checker"""
import os
import shutil

import pandas as pd

from cryptoboss import config as C

TMP = "/tmp/cryptoboss_checker_test"

WHALES = """Buying #SUI here

Long (10x-20x)

Entry: $0.8231

Reason: Chart looks bullish for it. Worth a long for short-mid term quick profits too.

Targets: $0.8643, 0.9055$, $0.9520,

Stop-loss: $0.7664"""
WHALES_SHORT = """Shorting #ZEC here

Short (10x-20x)

Entry: $529.80

Reason: Chart looks bearish for it. Worth a short for short-mid term quick profits too.

Targets: $513.80, 497.60$, $476.77,

Stop-loss: $574.39"""
QUEEN = """Coin: #LINKUSDT

Direction: Long

Leverage: 10x

Entry: 14.10$ - 13.90$

Targets: 14.50 - 14.90 - 15.40$

Stoploss: 13.40$"""
ORG = """Free Signal!

Moonriver Trade Signal (SWING)

Instrument: SOLUSDT
My opinion: Buy (Instant Execution)
Entry price: $95.5
Stop: $90
Target: $112
Our risk setting: 2%"""
BTC_K = "Buying #BTC here\nLong\nEntry: $81K\nTargets: $83K, $85K\nStop-loss: $77.5K"
BRAG = "#SUI Long Signal has achieved our 1st Target✅ 118% profit in 20x Leverage"
CHAT = "#BTC Daily Update: Well flushed down to $76,500 today before bouncing back to $78,460."


def test_parse():
    from cryptoboss.channels import parse
    a = parse(WHALES)
    assert a == {"coin": "SUI", "side": "long", "entry": 0.8231, "stop": 0.7664, "target": 0.8643}, a
    b = parse(WHALES_SHORT)
    assert b["side"] == "short" and b["coin"] == "ZEC" and b["target"] == 513.80, b
    q = parse(QUEEN)
    assert q["coin"] == "LINK" and q["side"] == "long" and abs(q["entry"] - 14.0) < 1e-9 and q["stop"] == 13.40, q
    o = parse(ORG)
    assert o["coin"] == "SOL" and o["entry"] == 95.5 and o["target"] == 112, o
    k = parse(BTC_K)
    assert k["entry"] == 81000 and k["stop"] == 77500 and k["target"] == 83000, k
    assert parse(BRAG) is None and parse(CHAT) is None
    print("parse OK")


def hours(start, rows):
    idx = pd.date_range(start, periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx).assign(Volume=1.0)


def test_grade():
    from cryptoboss.checker import grade_call
    t0 = pd.Timestamp("2026-11-01 10:00", tz="UTC")
    call = {"first_seen": t0.isoformat(), "side": "long", "entry": 10.0, "stop": 9.5, "target": 11.0, "status": "waiting"}
    # dips to entry, then hits the target
    b = hours(t0, [(10.3, 10.4, 10.2, 10.3), (10.2, 10.25, 9.95, 10.1), (10.2, 11.2, 10.1, 11.0)])
    r = grade_call(dict(call), b, t0 + pd.Timedelta(hours=5))
    assert r["status"] == "target" and 9 < r["pct_return"] < 10, r      # +10% minus the spread
    # entry and stop in the same candle -> loss
    r2 = grade_call(dict(call), hours(t0, [(10.2, 10.2, 9.4, 9.6)]), t0 + pd.Timedelta(hours=2))
    assert r2["status"] == "stop" and r2["pct_return"] < -5, r2
    # never comes back to the entry in 3 days
    r3 = grade_call(dict(call), hours(t0, [(10.5, 10.6, 10.4, 10.5)] * 80), t0 + pd.Timedelta(days=4))
    assert r3["status"] == "never_filled" and r3["pct_return"] == 0, r3
    # a short: price rises to entry, then falls to target
    sc = {**call, "side": "short", "entry": 10.0, "stop": 10.5, "target": 9.0}
    r4 = grade_call(sc, hours(t0, [(9.8, 10.05, 9.8, 10.0), (10.0, 10.1, 8.9, 9.0)]), t0 + pd.Timedelta(hours=3))
    assert r4["status"] == "target" and r4["pct_return"] > 9, r4
    # filled but nothing happens for 14 days -> sold at the last price
    flat = hours(t0, [(10.0, 10.05, 9.95, 10.02)] * (15 * 24))
    r5 = grade_call(dict(call), flat, t0 + pd.Timedelta(days=15))
    assert r5["status"] == "timeout", r5
    # still waiting
    r6 = grade_call(dict(call), b.iloc[:1], t0 + pd.Timedelta(hours=1))
    assert r6["status"] == "waiting", r6
    print("grade OK")


def test_run():
    from cryptoboss import channels, checker, notify
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    for k in ["CALLS_FILE", "CHECKER_STATE_FILE", "REPORT_FILE", "SIGNALS_FILE"]:
        setattr(C, k, os.path.join(TMP, os.path.basename(getattr(C, k))))
    sent = []
    notify.send = lambda t: sent.append(t) or True
    checker.load_channels = lambda: ["whalesguide", "WallstreetQueenOfficial"]
    feed = {"whalesguide": [{"id": 100, "text": CHAT}], "WallstreetQueenOfficial": [{"id": 7, "text": CHAT}]}
    checker.fetch_posts = lambda ch: feed[ch]
    checker.coinbase_coins = lambda: {"SUI", "ZEC", "LINK", "SOL", "BTC"}
    t0 = pd.Timestamp("2026-11-01 10:00", tz="UTC")
    market = {"SUI": hours(t0, [(0.85, 0.86, 0.84, 0.85), (0.84, 0.845, 0.82, 0.83), (0.83, 0.87, 0.83, 0.86)]),
              "ZEC": hours(t0, [(520, 531, 519, 530), (530, 580, 528, 575)]),
              "LINK": hours(t0, [(15, 15.1, 14.9, 15)] * 3)}
    checker.candles_since = lambda coin, start, now: market.get(coin, pd.DataFrame())[lambda d: d.index >= start] if coin in market else None

    # 1st run: only remembers where each channel is - old posts are NOT imported (we can't tell if losers were deleted)
    checker.run(now=t0)
    assert not os.path.exists(C.CALLS_FILE) or len(checker.load_calls()) == 0
    # new posts arrive
    feed["whalesguide"] += [{"id": 101, "text": WHALES}, {"id": 102, "text": WHALES_SHORT}, {"id": 103, "text": BRAG},
                            {"id": 104, "text": WHALES}]          # 104 = same call posted again
    feed["WallstreetQueenOfficial"] += [{"id": 8, "text": QUEEN}, {"id": 9, "text": "Buying #FOO\nEntry: 1\nTargets: 2\nStop-loss: 0.5"}]
    checker.run(now=t0)
    calls = checker.load_calls()
    assert len(calls) == 4, calls                              # SUI, ZEC, LINK, FOO (dupe + brag ignored)
    assert set(calls["robinhood"]) == {True, False}
    alerts = [s for s in sent if "SIGNAL CHECKER" in s and "called" in s]
    assert len(alerts) == 2 and all("CHECKING ONLY" in a for a in alerts), alerts   # SUI + LINK longs on Robinhood coins
    assert not any("ZEC" in a or "FOO" in a for a in alerts)
    # later: grade them
    checker.run(now=t0 + pd.Timedelta(hours=4))
    calls = checker.load_calls().set_index("coin")
    assert calls.loc["SUI", "status"] == "target" and calls.loc["ZEC", "status"] == "stop", calls
    assert calls.loc["FOO", "status"] == "no_data" and calls.loc["LINK", "status"] == "waiting"
    res = [s for s in sent if "results" in s]
    assert res and "SUI" in res[-1] and "ZEC" in res[-1], res
    text = checker.scoreboard_text(checker.load_calls())
    assert "whalesguide" in text and "Wallstreet" in text, text
    print("\n".join(sent))
    print("\n--- scoreboard ---\n" + text)
    print("run OK")


if __name__ == "__main__":
    test_parse()
    test_grade()
    test_run()
    print("ALL OK")
