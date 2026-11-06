"""Offline test for the Coach (no internet needed): python -m tests.test_coach"""
import pandas as pd


def rows(skill, rs, start="2026-11-01"):
    t = pd.date_range(start, periods=len(rs), freq="1h", tz="UTC")
    return [{"skill": skill, "status": "target" if r > 0 else "stop", "r_multiple": r,
             "exit_time": x.isoformat(), "published_at": x.isoformat()} for r, x in zip(rs, t)]


def test_coach():
    from cryptoboss import bot
    df = pd.DataFrame(rows("Dip Catcher", [-1.0, -0.5, 0.2])                # 3 trades, avg -0.43R -> benched fast
                      + rows("EMA Cross", [-1.0, -1.0])                     # only 2 trades: too few to judge
                      + rows("Band Bounce", [0.8, 0.5, -1.0, 0.9, 0.6])     # 5 trades avg +0.36R -> trusted
                      + rows("MACD 200", [-1.0] * 6 + [0.5] * 5)            # lost early, last 5 avg +0.5 -> back, trusted
                      + rows("VWAP Pullback", [0.0, 0.05, -0.1, 0.0])       # about even -> keeps learning
                      + [{"skill": "Triple Check", "status": "no_fill", "r_multiple": 0.0,
                          "exit_time": "2026-11-01T00:00:00+00:00", "published_at": "2026-11-01T00:00:00+00:00"}] * 30)
    assert bot.benched(df) == {"Dip Catcher"}, bot.benched(df)
    assert bot.trusted(df) == {"Band Bounce", "MACD 200"}, bot.trusted(df)
    text = bot.skills_text(df)
    assert text.index("Band Bounce") < text.index("Dip Catcher"), text                    # best skill first
    assert "Dip Catcher: 3 trades, win 33%, avg -0.43R, total -1.3R (BENCHED" in text, text
    assert "Band Bounce: 5 trades, win 80%, avg +0.36R, total +1.8R (TRUSTED" in text, text
    assert "Triple Check: no finished trades yet" in text, text
    print(text)
    print("coach OK")


def test_messages():
    """Benched skills stay quiet, trusted skills get full messages, learning skills share one short message."""
    from cryptoboss import bot, notify
    sigs = [{"coin": c, "skill": k, "entry": 1.0, "stop": 0.98, "target": 1.04, "risk_pct": 2.0, "reason": "x",
             "published_at": "2026-11-05T00:00:00+00:00", "max_hold": "4h"}
            for c, k in [("SOL", "Dip Catcher"), ("SOL", "Band Bounce"), ("DOGE", "EMA Cross"), ("PEPE", "Triple Check")]]
    text = bot.short_text(sigs[2:])
    assert text.count("\n") == 3 and "DOGE EMA Cross: buy if it climbs to" in text and "max 4h" in text, text
    print(text)


if __name__ == "__main__":
    test_coach()
    test_messages()
    print("ALL OK")
