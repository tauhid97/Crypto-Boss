"""Offline tests for the Telegram commands (no internet needed): python -m tests.test_commands"""
import os
import shutil

import pandas as pd

from cryptoboss import config as C

TMP = "/tmp/cryptoboss_commands_test"


def msg(uid, chat, text):
    return {"update_id": uid, "message": {"chat": {"id": chat, "type": "private"}, "text": text}}


def test_commands():
    from cryptoboss import bot, commands, notify
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    for k in ["SIGNALS_FILE", "COMMANDS_STATE_FILE"]:
        setattr(C, k, os.path.join(TMP, os.path.basename(getattr(C, k))))
    os.environ["TELEGRAM_CHAT_ID"] = "111"
    now = pd.Timestamp("2026-11-02 20:15", tz="UTC")
    bot.save_signals(pd.DataFrame([
        {"id": "a", "published_at": now.isoformat(), "coin": "SUI", "skill": "EMA Cross", "entry": 0.8231,
         "stop": 0.8100, "target": 0.8500, "status": "pending"},
        {"id": "b", "published_at": now.isoformat(), "coin": "PEPE", "skill": "Band Bounce", "entry": 0.00001,
         "stop": 0.0000098, "target": 0.0000104, "status": "open"},
        {"id": "c", "published_at": now.isoformat(), "coin": "LINK", "skill": "MACD 200", "entry": 14.0,
         "stop": 13.8, "target": 14.3, "status": "target", "r_multiple": 1.2},
    ]).reindex(columns=bot.COLS))

    sent, asked = [], []
    notify.send = lambda t: sent.append(t) or True
    inbox = [msg(10, 111, "/status"), msg(11, 111, "/calls"), msg(12, 111, "/scoreboard"),
             msg(13, 999, "/calls"),                       # a stranger: ignored, never answered
             msg(14, 111, "hello bot"), msg(15, 111, "/Status@CryptoBossTauhid_bot")]
    commands.get_updates = lambda offset: asked.append(offset) or [u for u in inbox if u["update_id"] >= (offset or 0)]

    commands.handle(now)
    assert asked == [None], asked
    assert len(sent) == 5, sent                             # 4 answers to Boss + help for "hello bot"; stranger ignored
    assert "awake" in sent[0].lower() and "Trades going now: 2" in sent[0] and "3:15 PM" in sent[0], sent[0]
    assert "+1.2R" in sent[0], sent[0]
    assert "SUI" in sent[1] and "PEPE" in sent[1] and "LINK" not in sent[1], sent[1]   # only trades still going
    assert "skill scoreboard" in sent[2].lower() and "MACD 200: 1 trades" in sent[2], sent[2]
    assert "/scoreboard" in sent[3] and "/calls" in sent[3]                       # unknown -> help
    assert "awake" in sent[4].lower()                                              # works with @botname too
    # next run: Telegram is told we already read up to 15, nothing is answered twice
    sent.clear()
    commands.handle(now + pd.Timedelta(minutes=15))
    assert asked[-1] == 16 and sent == [], (asked, sent)
    print("\n\n".join(sent) or "(nothing new)")
    print("commands OK")


def test_no_calls_yet():
    from cryptoboss import commands
    assert "none" in commands.calls_text(pd.DataFrame(columns=["status"])).lower()
    print("empty OK")


if __name__ == "__main__":
    test_commands()
    test_no_calls_yet()
    print("ALL OK")
