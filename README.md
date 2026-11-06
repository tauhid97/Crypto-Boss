# Crypto Boss: Boss's crypto checking bot

## The big idea (explained like you're 5)

Crypto Boss practice-trades crypto **24/7 with fake money**, using 7 scalping "skills". 5 of them
are the most-shared free strategies from YouTube (EMA Cross, MACD 200, Band Bounce, VWAP Pullback,
Triple Check), written down exactly so they can be graded fairly. Every 15 minutes it looks at the
5 wildest coins Robinhood sells and sends you any setups it finds.

A **Coach** keeps score for every skill: **quick to bench, slow to trust**.
- After just 3 finished trades, a skill whose last 10 trades average below -0.10R is **benched**: it keeps
  practicing quietly, but stops messaging you.
- A skill whose last 5 trades average above +0.10R is **trusted**: you get its full message.
- Every other skill is still **learning**: its trades come as short one-line messages.

**More practice = faster learning** (Nov 5, 2026): every skill may trade the same coin, up to 3 new
practice trades per skill per day and 30 in total.

**Wake-Up Rally** (added Nov 4, 2026) is borrowed from the stock bot. It checks *every* coin (not just
the 5 wildest): a coin down 15%+ in 60 days that suddenly jumps 3%+ today on 2x its usual volume. It buys
the new high of the day and may **hold up to 1 day**. In a test on Aug 2025 - Nov 2026 prices (fee
included) it was the only stock skill that won: 76 trades, about +0.45R each. It only fires a few times a
month, and past results are no promise.

**It never trades. It never uses real money.** Everything is PRACTICE. We wait 2-3 months of
good live results before even thinking about real money.

## What you'll get on Telegram (from your "Crypto Boss" bot)

| When | Message |
|---|---|
| A skill finds a setup | "CRYPTO BOSS [PRACTICE] - SOL ... Buy STOP ... Stop ... Target" |
| A practice trade ends | "results: SOL EMA Cross: TARGET HIT +1.6R" |
| Every night at ~9 PM New York time | Daily recap + the skill scoreboard |

**You can ask the bot things** (it answers within about 15 minutes): `/status`, `/calls`
(trades going now), `/scoreboard` (how each skill is doing). It only answers you.

## The fair rules

1. Only candles that finished **after** the signal count.
2. If stop and target could both hit in the same candle, it's a **loss**.
3. Robinhood's hidden **spread** (about 0.6% per round trip) is taken off every trade.
4. Not bought within 1 hour: cancelled. Still open after 4 hours: sold.

The old **Signal Checker** (grading public channels) is still in the code but switched off
(`SIGNAL_CHECKER = False` in config.py).

## Files

| File | What it is |
|---|---|
| `channels.txt` | The channels being watched. Add or remove names freely. |
| `coins.txt` | Coins Robinhood sells (check the app now and then). |
| `cryptoboss/skills.py` | The 7 scalping skills + the day skill Wake-Up Rally. |
| `cryptoboss/bot.py` | The 15-minute routine, the Coach, the messages. |
| `cryptoboss/checker.py` | The old channel referee (switched off). |
| `cryptoboss/channels.py` | Reads the channels' free public pages and pulls out the calls. |
| `cryptoboss/config.py` | All the settings. |
| `data/signals.csv` | Every practice trade, and how it ended (the bot writes this). |
| `docs/index.html` | The public scoreboard page (the bot writes this). |

## Costs

**Free**, as long as this GitHub project is **public**. It runs every 15 minutes on GitHub's free
robot. (A *private* project would use up GitHub's free minutes and could start charging.)

## Commands (Actions tab, then "Crypto Boss", then "Run workflow")

- `hello`: sends a test message to your Telegram
- `scoreboard`: sends the skill scoreboard right now
- `run`: one normal check
- `report`: rebuilds the scoreboard page

## Not financial advice

This is a learning tool. Free signal channels are often used for pump-and-dumps and to sell
"VIP" groups. Never send money or log in to anything a channel asks you to.
