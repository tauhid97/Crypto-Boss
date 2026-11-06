"""The 15-minute routine: judge open signals -> look for new ones -> message Boss -> daily recap."""
import json
import os

import pandas as pd

from . import config as C
from . import notify, report
from .data import daily, get_all
from .skills import DAY_SKILLS, KID_EXPLAINERS, find_day, find_new, money, prepare, weather
from .tracker import ACTIVE, settle

COLS = ["id", "published_at", "coin", "skill", "order_type", "entry", "stop", "target", "risk_pct",
        "reason", "status", "fill_time", "fill_price", "exit_time", "exit_price", "r_multiple", "pct_return",
        "entry_window", "max_hold"]
DISCLAIMER = ("Practice signals for learning only, not financial advice. Crypto is very risky and can "
              "drop fast. Past results do not guarantee future results.")
WORDS = {"target": "TARGET HIT", "stop": "STOPPED OUT", "timeout": "SOLD (time's up)", "no_fill": "NEVER BOUGHT"}


def load_coins():
    out = []
    for line in open(C.COINS_FILE):
        out += [c.strip().upper() for c in line.split("#")[0].split() if c.strip()]
    return list(dict.fromkeys(out))


def load_signals():
    if os.path.exists(C.SIGNALS_FILE):
        return pd.read_csv(C.SIGNALS_FILE, dtype={"status": "object", "fill_time": "object", "exit_time": "object"})
    return pd.DataFrame(columns=COLS)


def save_signals(df):
    os.makedirs(os.path.dirname(C.SIGNALS_FILE), exist_ok=True)
    df[COLS].to_csv(C.SIGNALS_FILE, index=False)


def load_state():
    return json.load(open(C.STATE_FILE)) if os.path.exists(C.STATE_FILE) else {}


def save_state(s):
    os.makedirs(os.path.dirname(C.STATE_FILE), exist_ok=True)
    json.dump(s, open(C.STATE_FILE, "w"), indent=1)


def et(ts):
    return pd.Timestamp(ts).tz_convert(C.TIMEZONE)


def signal_text(s, weather_note):
    pub = pd.Timestamp(s["published_at"])
    window, hold = (pd.Timedelta(s.get("entry_window") or C.ENTRY_WINDOW),
                    pd.Timedelta(s.get("max_hold") or C.MAX_HOLD))
    cancel = et(pub + window)
    return "\n".join([
        f"CRYPTO BOSS [{C.MODE}] - {s['coin']}",
        f"Skill: {s['skill']}",
        f"Buy STOP: only buy if the price climbs UP to {money(s['entry'])}",
        f"Stop (uh-oh, sell): {money(s['stop'])}",
        f"Target (yay, sell): {money(s['target'])}",
        f"Risk: {s['risk_pct']:.1f}% | Why: {s['reason']}",
        f"Cancel if not bought by {cancel:%I:%M %p} ET. Sell after {hold.total_seconds() / 3600:.0f} hours no matter what.",
        f"Crypto weather: {weather_note}",
        "",
        f"What this skill does: {KID_EXPLAINERS[s['skill']]}",
        "",
        DISCLAIMER])


def result_text(done):
    lines = [f"CRYPTO BOSS [{C.MODE}] - results"]
    for s in done:
        r = f"{s['r_multiple']:+.2f}R ({s['pct_return']:+.2f}%)" if s["status"] != "no_fill" else "no trade"
        lines.append(f"{s['coin']} {s['skill']}: {WORDS[s['status']]} - {r}")
    lines.append(f"(Robinhood's spread of about {C.SPREAD_PCT * 200:.1f}% per trade is already taken off.)")
    return "\n".join(lines)


def recap_text(df, day, top, note):
    done = df[~df["status"].isin(ACTIVE)].copy()
    done["day"] = [et(t).strftime("%Y-%m-%d") for t in done["exit_time"]]
    today = done[done["day"] == day]
    traded = done[done["status"] != "no_fill"]
    lines = [f"CRYPTO BOSS [{C.MODE}] - daily recap for {day}", ""]
    t_traded = today[today["status"] != "no_fill"]
    if len(t_traded):
        wins = (t_traded["r_multiple"] > 0).sum()
        lines.append(f"Today: {len(t_traded)} trades, {wins} wins, total {t_traded['r_multiple'].sum():+.2f}R")
    else:
        lines.append("Today: no trades finished.")
    if len(traded):
        lines.append(f"All time: {len(traded)} trades, win {100 * (traded['r_multiple'] > 0).mean():.0f}%, "
                     f"avg {traded['r_multiple'].mean():+.2f}R, total {traded['r_multiple'].sum():+.1f}R")
    lines += [f"Wildest coins right now: {', '.join(top) or 'none'}", f"Crypto weather: {note}", "",
              "Still PRACTICE. We wait for 2-3 months of good results before any real money."]
    return "\n".join(lines)


def skill_stats(df):
    """Every skill's finished practice trades: [{skill, trades, win, avg, total, benched, trusted}], best first."""
    from .skills import ALL_SKILLS
    traded = df[df["status"].isin(["target", "stop", "timeout"])]
    if "exit_time" in traded:
        traded = traded.assign(_t=pd.to_datetime(traded["exit_time"], utc=True, errors="coerce")).sort_values(
            "_t", kind="stable")
    out = []
    for name in ALL_SKILLS:
        g = traded[traded["skill"] == name]
        n = len(g)
        r = g["r_multiple"].astype(float)
        avg = float(r.mean()) if n else None
        trust = n >= C.COACH_TRUST_TRADES and r.tail(C.COACH_TRUST_TRADES).mean() > C.COACH_TRUST_R
        bench = (not trust and n >= C.COACH_BENCH_TRADES
                 and r.tail(C.COACH_LOOKBACK).mean() < C.COACH_BENCH_R)
        out.append({"skill": name, "trades": n, "win": 100 * float((r > 0).mean()) if n else None,
                    "avg": avg, "total": float(r.sum()) if n else 0.0,
                    "benched": bool(bench), "trusted": bool(trust)})
    return sorted(out, key=lambda s: (s["trades"] > 0, s["total"]), reverse=True)


def benched(df):
    return {s["skill"] for s in skill_stats(df) if s["benched"]}


def trusted(df):
    return {s["skill"] for s in skill_stats(df) if s["trusted"]}


def short_text(signals):
    """Learning skills' signals: one short line each, all in one message, so Telegram stays readable."""
    lines = [f"CRYPTO BOSS [{C.MODE}] - learning skills' practice trades (short form)"]
    for s in signals:
        hold = pd.Timedelta(s.get("max_hold") or C.MAX_HOLD).total_seconds() / 3600
        lines.append(f"{s['coin']} {s['skill']}: buy if it climbs to {money(s['entry'])}, "
                     f"stop {money(s['stop'])}, target {money(s['target'])}, max {hold:.0f}h")
    lines.append("These skills are still learning. The Coach sends full messages once a skill has earned trust.")
    return "\n".join(lines)


def skills_text(df):
    lines = [f"CRYPTO BOSS [{C.MODE}] - skill scoreboard", ""]
    for s in skill_stats(df):
        if not s["trades"]:
            lines.append(f"{s['skill']}: no finished trades yet")
            continue
        tag = " (BENCHED - losing)" if s["benched"] else " (TRUSTED - winning lately)" if s["trusted"] else ""
        lines.append(f"{s['skill']}: {s['trades']} trades, win {s['win']:.0f}%, avg {s['avg']:+.2f}R, "
                     f"total {s['total']:+.1f}R{tag}")
    lines += ["", f"Coach: quick to bench, slow to trust. Benched = {C.COACH_BENCH_TRADES}+ trades and its last "
              f"{C.COACH_LOOKBACK} average below {C.COACH_BENCH_R:+.2f}R (keeps practicing quietly). Trusted = last "
              f"{C.COACH_TRUST_TRADES} average above {C.COACH_TRUST_R:+.2f}R (full messages). The rest send short lines.",
              "R = what we risked: +1R means we won what we risked."]
    return "\n".join(lines)


def run(now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    state = load_state()
    frames = get_all(load_coins(), now)
    if not frames:
        day = et(now).strftime("%Y-%m-%d")
        print("No price data this time.")
        if state.get("data_alert") != day:
            notify.send("Boss, Crypto Boss couldn't get crypto prices just now. I'll keep trying every 15 minutes.")
            state["data_alert"] = day
            save_state(state)
        return
    frames = {c: prepare(df) for c, df in frames.items()}
    df = load_signals()
    changed, done = False, []

    # 1) Judge: update every signal that is still waiting or open
    for i in df.index[df["status"].isin(ACTIVE)]:
        row = df.loc[i].to_dict()
        if row["coin"] not in frames:
            continue
        new = settle(dict(row), frames[row["coin"]], now)
        if new["status"] != row["status"]:
            for k, v in new.items():
                df.at[i, k] = v
            changed = True
            if new["status"] not in ACTIVE:
                done.append(new)

    # 2) Scout: look for new signals (one active signal per coin per skill, a cooldown, and daily caps)
    cool = now - pd.Timedelta(C.COOLDOWN)
    today = now.floor("1D")
    pairs = list(zip(df["coin"], df["skill"], df["published_at"], df["status"]))
    blocked = {(c, k) for c, k, t, st in pairs if st in ACTIVE or pd.Timestamp(t) > cool}
    made = pd.Series([k for c, k, t, st in pairs if pd.Timestamp(t) >= today], dtype=object).value_counts()
    left = {k: C.SKILL_DAILY_CAP - int(n) for k, n in made.items()}
    room = C.DAILY_CAP - int(made.sum())
    if room > 0:
        new_sigs, w, note = find_new(frames, now, blocked, left, room)
    else:
        new_sigs, (w, note) = [], weather(frames, now)
    # day skills (Wake-Up Rally): every coin, at most once per coin per UTC day
    skip = {(c, k) for c, k, t, st in pairs if pd.Timestamp(t) >= today}
    busy = {c for c, k, t, st in pairs if st in ACTIVE and k in DAY_SKILLS}   # a day skill already in this coin
    if room - len(new_sigs) > 0:
        new_sigs += find_day(frames, daily, now, busy, skip)
    for s in new_sigs:
        s.update(id=f"{now:%Y%m%d%H%M}-{s['coin']}", published_at=now.isoformat(), status="pending")
        df = pd.concat([df, pd.DataFrame([s])], ignore_index=True) if len(df) else pd.DataFrame([s])
        changed = True

    for c in COLS:
        if c not in df:
            df[c] = None
    if changed:
        save_signals(df)
    bench, trust = benched(df), trusted(df)
    short = []
    for s in new_sigs:
        text = signal_text(s, note)
        print(text, "\n")
        if s["skill"] in bench:                # benched skills practice quietly
            continue
        if s["skill"] in trust:                # trusted skills get the full message
            notify.send(text)
        else:
            short.append(s)
    if len(short) == 1:                        # just one: the full message is still easy to read
        notify.send(signal_text(short[0], note))
    elif short:
        notify.send(short_text(short))
    if done:
        text = result_text(done)
        print(text)
        notify.send(text)

    # 3) Daily recap at about 9 PM New York time
    local = et(now)
    day = local.strftime("%Y-%m-%d")
    if local.hour >= C.RECAP_HOUR and state.get("recap") != day:
        from .skills import wildest
        text = recap_text(df, day, wildest(frames, now), note) + "\n\n" + skills_text(df)
        print(text)
        notify.send(text)
        state["recap"] = day
        save_state(state)
        changed = True
    if changed:
        report.build(df)
