"""Offline tests for the Telegram commands (no internet needed): python -m tests.test_commands"""
import os
import shutil

import pandas as pd

from cryptoboss import config as C

TMP = "/tmp/cryptoboss_commands_test"


def msg(uid, chat, text):
    return {"update_id": uid, "message": {"chat": {"id": chat, "type": "private"}, "text": text}}


def test_commands():
    from cryptoboss import checker, commands, notify
    shutil.rmtree(TMP, ignore_errors=True); os.makedirs(TMP)
    for k in ["CALLS_FILE", "CHECKER_STATE_FILE", "COMMANDS_STATE_FILE"]:
        setattr(C, k, os.path.join(TMP, os.path.basename(getattr(C, k))))
    os.environ["TELEGRAM_CHAT_ID"] = "111"
    now = pd.Timestamp("2026-11-02 20:15", tz="UTC")
    checker.save_calls(pd.DataFrame([
        {"id": "a", "channel": "whalesguide", "post_id": 1, "first_seen": now.isoformat(), "coin": "SUI", "side": "long",
         "entry": 0.8231, "stop": 0.7664, "target": 0.8643, "robinhood": True, "status": "waiting"},
        {"id": "b", "channel": "whalesguide", "post_id": 2, "first_seen": now.isoformat(), "coin": "ZEC", "side": "short",
         "entry": 529.8, "stop": 574.39, "target": 513.8, "robinhood": False, "status": "open", "fill_price": 529.8},
        {"id": "c", "channel": "cryptosignals0rg", "post_id": 3, "first_seen": now.isoformat(), "coin": "LINK", "side": "long",
         "entry": 14.0, "stop": 13.4, "target": 14.5, "robinhood": True, "status": "target", "pct_return": 2.97},
    ]).assign(**{c: None for c in ["fill_time", "exit_time", "exit_price"]}).reindex(columns=checker.COLS))
    checker.save_state({"last_id": {"whalesguide": 5, "cryptosignals0rg": 9}})

    sent, asked = [], []
    notify.send = lambda t: sent.append(t) or True
    inbox = [msg(10, 111, "/status"), msg(11, 111, "/calls"), msg(12, 111, "/scoreboard"),
             msg(13, 999, "/calls"),                       # a stranger: ignored, never answered
             msg(14, 111, "hello bot"), msg(15, 111, "/Status@CryptoBossTauhid_bot")]
    commands.get_updates = lambda offset: asked.append(offset) or [u for u in inbox if u["update_id"] >= (offset or 0)]

    commands.handle(now)
    assert asked == [None], asked
    assert len(sent) == 5, sent                             # 4 answers to Boss + help for "hello bot"; stranger ignored
    assert "awake" in sent[0].lower() and "2" in sent[0] and "3:15 PM" in sent[0], sent[0]
    assert "SUI" in sent[1] and "ZEC" in sent[1] and "LINK" not in sent[1], sent[1]   # only calls still going
    assert "scoreboard" in sent[2].lower() and "cryptosignals0rg" in sent[2]
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
