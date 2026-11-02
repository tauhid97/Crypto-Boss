"""SIGNAL CHECKER - watches free public channels and grades every trade call they post.

Honest rules:
- A call counts from the moment WE first see it (not the time the channel claims).
- Old posts from before we started watching are never imported (deleted losers would be missing).
- A deleted post stays in our record.
- Grading is strict: one-hour candles, stop counted first if both could have hit, no leverage,
  and Robinhood's spread taken off. Only the FIRST target counts.
- "Robinhood-usable" = a BUY call on a coin Robinhood sells. Sell/short calls are graded too,
  so we know how good the channel is, but Robinhood can't do them.
"""
import json
import os

import pandas as pd
import requests

from . import config as C
from . import notify
from .channels import fetch_posts, parse
from .data import _get
from .skills import money

COLS = ["id", "channel", "post_id", "first_seen", "coin", "side", "entry", "stop", "target", "robinhood",
        "status", "fill_time", "fill_price", "exit_time", "exit_price", "pct_return"]
ACTIVE = {"waiting", "open"}
HOUR = pd.Timedelta("1h")
WORDS = {"target": "TARGET HIT", "stop": "STOPPED OUT", "timeout": "SOLD (14 days up)",
         "never_filled": "PRICE NEVER REACHED ENTRY"}


def load_channels():
    out = []
    for line in open(C.CHANNELS_FILE):
        out += [c.strip().lstrip("@") for c in line.split("#")[0].split() if c.strip()]
    return list(dict.fromkeys(out))


def robinhood_coins():
    out = set()
    for line in open(C.COINS_FILE):
        out |= {c.strip().upper() for c in line.split("#")[0].split() if c.strip()}
    return out


def coinbase_coins():
    r = requests.get("https://api.exchange.coinbase.com/products", timeout=20, headers={"User-Agent": "crypto-boss-bot"})
    r.raise_for_status()
    return {p["base_currency"] for p in r.json() if p["quote_currency"] == "USD" and p.get("status") == "online"}


def candles_since(coin, start, now):
    parts, t = [], start
    while t < now:
        t2 = min(t + HOUR * 299, now)
        df = _get(coin, t, t2, step=HOUR)
        if df is not None:
            parts.append(df)
        t = t2
    if not parts:
        return None
    df = pd.concat(parts)
    return df[~df.index.duplicated()].sort_index()


def load_calls():
    if os.path.exists(C.CALLS_FILE):
        return pd.read_csv(C.CALLS_FILE, dtype={"status": "object", "fill_time": "object", "exit_time": "object"})
    return pd.DataFrame(columns=COLS)


def save_calls(df):
    os.makedirs(os.path.dirname(C.CALLS_FILE), exist_ok=True)
    df[COLS].to_csv(C.CALLS_FILE, index=False)


def load_state():
    return json.load(open(C.CHECKER_STATE_FILE)) if os.path.exists(C.CHECKER_STATE_FILE) else {}


def save_state(s):
    os.makedirs(os.path.dirname(C.CHECKER_STATE_FILE), exist_ok=True)
    json.dump(s, open(C.CHECKER_STATE_FILE, "w"), indent=1)


def _finish(call, price, ts, status):
    fill = call["fill_price"]
    if call["side"] == "long":
        pct = price * (1 - C.SPREAD_PCT) / (fill * (1 + C.SPREAD_PCT)) - 1
    else:
        pct = (fill - price) / fill - 2 * C.SPREAD_PCT
    call.update(status=status, exit_price=float(price), exit_time=ts.isoformat(), pct_return=round(pct * 100, 3))
    return call


def grade_call(call, bars, now):
    """Follow one call hour by hour. Returns the updated dict."""
    seen = pd.Timestamp(call["first_seen"])
    long = call["side"] == "long"
    entry, stop, target = call["entry"], call["stop"], call["target"]
    filled = pd.Timestamp(call["fill_time"]) if call.get("status") == "open" else None
    for ts, b in bars[bars.index >= seen.floor("h")].iterrows():
        if ts + HOUR > now:
            break
        if filled is None:
            if ts >= seen + pd.Timedelta(C.CALL_ENTRY_WINDOW):
                call.update(status="never_filled", pct_return=0.0, exit_time=ts.isoformat())
                return call
            if not (b["Low"] <= entry if long else b["High"] >= entry):
                continue
            filled = ts
            call.update(status="open", fill_time=ts.isoformat(),
                        fill_price=float(min(entry, b["Open"]) if long else max(entry, b["Open"])))
            if (b["Low"] <= stop) if long else (b["High"] >= stop):     # stopped in the same hour
                return _finish(call, stop, ts, "stop")
            continue
        if ts >= filled + pd.Timedelta(C.CALL_MAX_HOLD):
            return _finish(call, b["Close"], ts, "timeout")
        if long and b["Low"] <= stop:
            return _finish(call, min(stop, b["Open"]), ts, "stop")
        if not long and b["High"] >= stop:
            return _finish(call, max(stop, b["Open"]), ts, "stop")
        if (b["High"] >= target) if long else (b["Low"] <= target):
            return _finish(call, target, ts, "target")
    return call


def alert_text(c):
    side = "BUY" if c["side"] == "long" else "SELL/SHORT"
    return "\n".join([
        f"SIGNAL CHECKER - @{c['channel']} called: {side} {c['coin']}",
        f"Entry {money(c['entry'])} | Stop {money(c['stop'])} | Target {money(c['target'])}",
        "CHECKING ONLY - we're grading this channel, not following it. Don't trade it.",
        "I'll tell you how it ends."])


def finished_text(done):
    lines = ["SIGNAL CHECKER - results"]
    for c in done:
        side = "buy" if c["side"] == "long" else "short"
        r = f"{c['pct_return']:+.2f}%" if c["status"] not in ("never_filled",) else "no trade"
        lines.append(f"@{c['channel']} {c['coin']} {side}: {WORDS[c['status']]} - {r}")
    lines.append(f"(No leverage. Robinhood's spread of about {C.SPREAD_PCT * 200:.1f}% is taken off.)")
    return "\n".join(lines)


def channel_stats(calls):
    rows = []
    for ch, g in calls.groupby("channel"):
        done = g[g["status"].isin(["target", "stop", "timeout"])]
        rh = done[done["robinhood"].astype(bool)]
        rows.append({"channel": ch, "calls": len(g), "graded": len(done),
                     "win": 100 * (done["pct_return"] > 0).mean() if len(done) else None,
                     "avg": done["pct_return"].mean() if len(done) else None,
                     "total": done["pct_return"].sum() if len(done) else 0.0,
                     "rh_calls": int(g["robinhood"].astype(bool).sum()),
                     "rh_avg": rh["pct_return"].mean() if len(rh) else None})
    return rows


def scoreboard_text(calls):
    lines = ["SIGNAL CHECKER - channel scoreboard (practice, no leverage, spread included)", ""]
    if not len(calls):
        return "\n".join(lines + ["No calls seen yet. Watching..."])
    for s in sorted(channel_stats(calls), key=lambda s: -(s["avg"] if s["avg"] is not None else -999)):
        if s["graded"]:
            lines.append(f"@{s['channel']}: {s['graded']} graded of {s['calls']} calls, win {s['win']:.0f}%, "
                         f"avg {s['avg']:+.2f}% per trade, total {s['total']:+.1f}%")
        else:
            lines.append(f"@{s['channel']}: {s['calls']} calls, none finished yet")
        rh = f"avg {s['rh_avg']:+.2f}%" if s["rh_avg"] is not None else "none finished"
        lines.append(f"   Robinhood-usable buys: {s['rh_calls']} ({rh})")
    lines += ["", f"A channel needs a good record for 2-3 months before we even think about following it."]
    return "\n".join(lines)


def run(now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    state = load_state()
    last = state.setdefault("last_id", {})
    calls = load_calls()
    changed, alerts, done = False, [], []
    try:
        on_coinbase = coinbase_coins()
    except Exception as e:
        print("Coinbase coin list failed:", e)
        on_coinbase = None
    rh = robinhood_coins()

    # 1) read each channel's newest posts
    for ch in load_channels():
        try:
            posts = fetch_posts(ch)
        except Exception as e:
            print(f"@{ch}: couldn't read ({e})")
            continue
        if not posts:
            continue
        if ch not in last:                         # first time: start from now, don't import old posts
            last[ch] = max(p["id"] for p in posts)
            print(f"@{ch}: now watching (starting after post {last[ch]})")
            changed = True
            continue
        for p in [p for p in posts if p["id"] > last[ch]]:
            c = parse(p["text"])
            last[ch] = max(last[ch], p["id"])
            changed = True
            if not c:
                continue
            dupe = ((calls["channel"] == ch) & (calls["coin"] == c["coin"]) &
                    ((calls["entry"] - c["entry"]).abs() < 1e-12)).any() if len(calls) else False
            if dupe:
                continue
            row = {**c, "id": f"{ch}-{p['id']}", "channel": ch, "post_id": p["id"], "first_seen": now.isoformat(),
                   "robinhood": bool(c["side"] == "long" and c["coin"] in rh),
                   "status": "waiting" if on_coinbase is None or c["coin"] in on_coinbase else "no_data"}
            calls = pd.concat([calls, pd.DataFrame([row])], ignore_index=True) if len(calls) else pd.DataFrame([row])
            if row["robinhood"]:
                alerts.append(row)

    # 2) grade every call that's still going
    for i in calls.index[calls["status"].isin(ACTIVE)]:
        row = calls.loc[i].to_dict()
        try:
            bars = candles_since(row["coin"], pd.Timestamp(row["first_seen"]).floor("h"), now)
        except Exception as e:
            print(f"{row['coin']}: price error ({e})")
            continue
        if bars is None:
            calls.at[i, "status"] = "no_data"
            changed = True
            continue
        new = grade_call(dict(row), bars, now)
        if new["status"] != row["status"]:
            for k, v in new.items():
                calls.at[i, k] = v
            changed = True
            if new["status"] not in ACTIVE:
                done.append(new)

    for c in COLS:
        if c not in calls:
            calls[c] = None
    if changed:
        save_calls(calls)
    for a in alerts:
        notify.send(alert_text(a))
    if done:
        notify.send(finished_text(done))

    # 3) daily channel scoreboard at about 9 PM New York time
    local = now.tz_convert(C.TIMEZONE)
    day = local.strftime("%Y-%m-%d")
    if local.hour >= C.RECAP_HOUR and state.get("recap") != day:
        notify.send(scoreboard_text(calls))
        state["recap"] = day
        changed = True
    if changed:
        save_state(state)
        from . import bot, report
        report.build(bot.load_signals(), calls)
    return calls
