"""COMMANDS - answers Boss when he types to the Crypto Boss bot.

The bot only wakes up every ~15 minutes, so answers can take that long. It only ever
answers Boss's own chat (TELEGRAM_CHAT_ID); messages from anyone else are ignored.

  /status       am I awake, when did I last check, how are the practice trades doing
  /calls        the practice trades still waiting or open
  /scoreboard   the skill scoreboard right now
  anything else this help message
"""
import json
import os

import pandas as pd
import requests

from . import config as C
from . import notify
from .bot import load_signals, skills_text
from .skills import SKILLS, money
from .tracker import ACTIVE

HELP = ("Hi Boss! I wake up about every 15 minutes, so my answers can take that long.\n"
        "Things you can ask me:\n"
        "/status - am I working, and how is practice going\n"
        "/calls - the practice trades still waiting or open\n"
        "/scoreboard - how each skill is doing")


def get_updates(offset):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    if not tok:
        return []
    params = {"timeout": 0, "allowed_updates": json.dumps(["message"])}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", params=params, timeout=20)
    return r.json().get("result", []) if r.ok else []


def status_text(sigs, now):
    active = sigs[sigs["status"].isin(ACTIVE)]
    done = sigs[sigs["status"].isin(["target", "stop", "timeout"])]
    t = now.tz_convert(C.TIMEZONE)
    lines = [f"I'm awake, Boss! Checked at {t:%I:%M %p} ET ({t:%a %b %d}).".replace(" 0", " "),
             f"Practice scalping with {len(SKILLS)} skills on the wildest Robinhood coins, 24/7.",
             f"Trades going now: {len(active)} ({(active['status'] == 'pending').sum()} waiting to buy, "
             f"{(active['status'] == 'open').sum()} bought)."]
    if len(done):
        lines.append(f"Finished so far: {len(done)}, win {100 * (done['r_multiple'] > 0).mean():.0f}%, "
                     f"total {done['r_multiple'].sum():+.1f}R.")
    else:
        lines.append("No finished trades yet.")
    lines.append("Everything is PRACTICE - no real money.")
    return "\n".join(lines)


def calls_text(sigs):
    active = sigs[sigs["status"].isin(ACTIVE)]
    if not len(active):
        return "No practice trades going right now - none are waiting or open."
    lines = [f"Practice trades going now ({len(active)}):", ""]
    for _, c in active.head(15).iterrows():
        where = "bought" if c["status"] == "open" else "waiting to buy"
        lines.append(f"{c['coin']} ({c['skill']}) - {where}")
        lines.append(f"   Entry {money(c['entry'])} | Stop {money(c['stop'])} | Target {money(c['target'])}")
    if len(active) > 15:
        lines.append(f"...and {len(active) - 15} more.")
    return "\n".join(lines)


def answer(text, sigs, now):
    word = (text or "").strip().split()[0].split("@")[0].lower() if (text or "").strip() else ""
    if word == "/status":
        return status_text(sigs, now)
    if word == "/calls":
        return calls_text(sigs)
    if word == "/scoreboard":
        return skills_text(sigs)
    return HELP


def handle(now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    boss = str(os.getenv("TELEGRAM_CHAT_ID") or "")
    state = json.load(open(C.COMMANDS_STATE_FILE)) if os.path.exists(C.COMMANDS_STATE_FILE) else {}
    offset = state.get("next_update")
    updates = get_updates(offset)
    if not updates:
        return
    sigs = load_signals()
    for u in sorted(updates, key=lambda u: u["update_id"]):
        m = u.get("message") or {}
        if boss and str((m.get("chat") or {}).get("id")) == boss and "text" in m:
            notify.send(answer(m["text"], sigs, now))
    state["next_update"] = max(u["update_id"] for u in updates) + 1
    os.makedirs(os.path.dirname(C.COMMANDS_STATE_FILE), exist_ok=True)
    json.dump(state, open(C.COMMANDS_STATE_FILE, "w"), indent=1)
