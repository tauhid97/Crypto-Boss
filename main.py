"""Command center for Crypto Boss.

  python main.py run            # the 15-minute routine (used by the schedule): Signal Checker
                                #   (+ quick trades, only if QUICK_TRADES = True in config.py)
  python main.py scoreboard     # send the channel scoreboard to your Telegram now
  (every run also answers Boss's /status, /calls and /scoreboard messages to the bot)
  python main.py hello          # send a test message to your Crypto Boss Telegram
  python main.py backtest 30    # practice on the last 30 days (prints the results, also sends them to Telegram)
  python main.py report         # rebuild the scoreboard page
"""
import sys

from cryptoboss import backtest, bot, checker, commands, data, notify, report
from cryptoboss import config as C


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        if C.QUICK_TRADES:
            bot.run()
        checker.run()
        try:
            commands.handle()
        except Exception as e:             # a Telegram hiccup must never stop the results being saved
            print("Commands skipped:", e)
    elif cmd == "scoreboard":
        notify.send(checker.scoreboard_text(checker.load_calls()))
    elif cmd == "hello":
        ok = notify.send(f"Hi Boss! {C.BRAND_NAME} is connected. The Signal Checker is watching free channels 24/7 and will report here.")
        print("Sent!" if ok else "Telegram secrets are missing - see README.")
    elif cmd == "backtest":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        market = {c: df for c in bot.load_coins() if (df := data.history(c, days + 2)) is not None}
        _, text = backtest.run(market, days)
        print(text)
        notify.send("Boss, here's the Crypto Boss practice-on-the-past check:\n" + text)
    elif cmd == "report":
        report.build(bot.load_signals())
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
