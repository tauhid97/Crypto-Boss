"""Offline test for the Coach (no internet needed): python -m tests.test_coach"""
import pandas as pd


def test_coach():
    from cryptoboss import bot
    rows = ([{"skill": "Dip Catcher", "status": "stop", "r_multiple": -1.0}] * 20          # 20 losses -> benched
            + [{"skill": "EMA Cross", "status": "stop", "r_multiple": -1.0}] * 5          # too few to judge yet
            + [{"skill": "Band Bounce", "status": "target", "r_multiple": 0.8}] * 25      # winning -> plays on
            + [{"skill": "MACD 200", "status": "no_fill", "r_multiple": 0.0}] * 30)       # never bought: not counted
    df = pd.DataFrame(rows)
    assert bot.benched(df) == {"Dip Catcher"}, bot.benched(df)
    text = bot.skills_text(df)
    assert text.index("Band Bounce") < text.index("Dip Catcher"), text                    # best skill first
    assert "Dip Catcher: 20 trades, win 0%, avg -1.00R, total -20.0R (BENCHED" in text, text
    assert "MACD 200: no finished trades yet" in text, text
    print("coach OK")


if __name__ == "__main__":
    test_coach()
    print("ALL OK")
