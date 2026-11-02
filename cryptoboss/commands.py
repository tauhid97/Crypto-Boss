"""COMMANDS - answers Boss when he types to the Crypto Boss bot.

The bot only wakes up every ~15 minutes, so answers can take that long. It only ever
answers Boss's own chat (TELEGRAM_CHAT_ID); messages from anyone else are ignored.

  /status       am I awake, when did I last check, how many calls am I following
  /calls        the calls still waiting or in a trade
  /scoreboard   the channel scoreboard right now
  anything else this help message
"""
import json
import os

import pandas as pd
import requests

from . import config as C
from . import notify
from .checker import ACTIVE, load_calls, load_state, scoreboard_text
from .skills import money

HELP = ("Hi Boss! I wake up about every 15 minutes, so my answers can take that long.\n"
        "Things you can ask me:\n"
        "/status - am I working, and what am I watching\n"
        "/calls - the calls I'm still following\n"
        "/scoreboard - how each channel is doing")


def get_updates(offset):
    tok = os.getenv("TELEGRAM_BOT_TOKEN")
    if not tok:
        return []
    params = {"timeout": 0, "allowed_updates": json.dumps(["message"])}
    if offset is not None:
        params["offset"] = offset
    r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", params=params, timeout=20)
    return r.json().get("result", []) if r.ok else []


def status_text(calls, now):
    active = calls[calls["status"].isin(ACTIVE)]
    done = calls[calls["status"].isin(["target", "stop", "timeout"])]
    watching = len(load_state().get("last_id", {}))
    t = now.tz_convert(C.TIMEZONE)
    return "\n".join([
        f"I'm awake, Boss! Checked at {t:%I:%M %p} ET ({t:%a %b %d}).".replace(" 0", " "),
        f"Watching {watching} channels.",
        f"Calls I'm following: {len(active)} ({(active['status'] == 'waiting').sum()} waiting for their entry, "
        f"{(active['status'] == 'open').sum()} in a trade).",
        f"Finished and graded so far: {len(done)}.",
        "Everything is PRACTICE - no real money."])


def calls_text(calls):
    active = calls[calls["status"].isin(ACTIVE)]
    if not len(active):
        return "No calls I'm following right now - none are waiting or open."
    lines = [f"Calls I'm following ({len(active)}):", ""]
    for _, c in active.head(15).iterrows():
        side = "BUY" if c["side"] == "long" else "SHORT"
        where = "in the trade" if c["status"] == "open" else "waiting for entry"
        rh = "" if c["robinhood"] in (True, "True") else " (not doable on Robinhood)"
        lines.append(f"@{c['channel']}: {side} {c['coin']} - {where}{rh}")
        lines.append(f"   Entry {money(c['entry'])} | Stop {money(c['stop'])} | Target {money(c['target'])}")
    if len(active) > 15:
        lines.append(f"...and {len(active) - 15} more.")
    return "\n".join(lines)


def answer(text, calls, now):
    word = (text or "").strip().split()[0].split("@")[0].lower() if (text or "").strip() else ""
    if word == "/status":
        return status_text(calls, now)
    if word == "/calls":
        return calls_text(calls)
    if word == "/scoreboard":
        return scoreboard_text(calls)
    return HELP


def handle(now=None):
    now = now or pd.Timestamp.now(tz="UTC")
    boss = str(os.getenv("TELEGRAM_CHAT_ID") or "")
    state = json.load(open(C.COMMANDS_STATE_FILE)) if os.path.exists(C.COMMANDS_STATE_FILE) else {}
    offset = state.get("next_update")
    updates = get_updates(offset)
    if not updates:
        return
    calls = load_calls()
    for u in sorted(updates, key=lambda u: u["update_id"]):
        m = u.get("message") or {}
        if boss and str((m.get("chat") or {}).get("id")) == boss and "text" in m:
            notify.send(answer(m["text"], calls, now))
    state["next_update"] = max(u["update_id"] for u in updates) + 1
    os.makedirs(os.path.dirname(C.COMMANDS_STATE_FILE), exist_ok=True)
    json.dump(state, open(C.COMMANDS_STATE_FILE, "w"), indent=1)
