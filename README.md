# Crypto Boss: Boss's crypto checking bot

## The big idea (explained like you're 5)

Lots of free Telegram channels shout "BUY THIS COIN!" Some are honest, many are not.
Crypto Boss is a **referee**. It watches those channels all day and night, writes down every
trade call the moment it sees one, and checks later: **did that call actually make money?**

After 2-3 months you'll know which channels (if any) are really good, with proof.

**It never trades. It never uses real money.** Everything is PRACTICE.

## What you'll get on Telegram (from your "Crypto Boss" bot)

| When | Message |
|---|---|
| A channel posts a **buy** call on a coin Robinhood sells | "SIGNAL CHECKER - @channel called: BUY SOL ... CHECKING ONLY" |
| A call finishes | "SIGNAL CHECKER - results: SOL buy: TARGET HIT +4.4%" |
| Every night at ~9 PM New York time | The channel scoreboard: who's winning, who's losing |

Sell/short calls and coins Robinhood doesn't have are graded quietly, without a message, so the
scoreboard is fair. They're not messaged because you can't do them on Robinhood.

## The referee's rules (so nobody can cheat)

1. A call counts from the moment **we** first see it. Old posts are never imported.
2. If a channel deletes a losing call later, **we still have it**.
3. **No leverage.** Channels say "10x-20x" (borrowed money). We grade the plain coin.
4. Only the **first target** counts. If the stop and target could both have hit in the same hour, it's a **loss**.
5. Robinhood's hidden **spread** (about 0.6% per trade) is taken off every result.
6. If the price never reaches the entry within 3 days: "never filled", no win, no loss.
7. If a trade is still open after 14 days, it's sold at that day's price.

## Files

| File | What it is |
|---|---|
| `channels.txt` | The channels being watched. Add or remove names freely. |
| `coins.txt` | Coins Robinhood sells (check the app now and then). |
| `cryptoboss/checker.py` | The referee. |
| `cryptoboss/channels.py` | Reads the channels' free public pages and pulls out the calls. |
| `cryptoboss/config.py` | All the settings. |
| `data/channel_calls.csv` | Every call ever seen, and how it ended (the bot writes this). |
| `docs/index.html` | The public scoreboard page (the bot writes this). |
| `cryptoboss/skills.py`, `bot.py` | The old quick-trades bot. **Switched OFF** because it lost money in testing. |

## Costs

**Free**, as long as this GitHub project is **public**. It runs every 15 minutes on GitHub's free
robot. (A *private* project would use up GitHub's free minutes and could start charging.)

## Commands (Actions tab, then "Crypto Boss", then "Run workflow")

- `hello`: sends a test message to your Telegram
- `scoreboard`: sends the scoreboard right now
- `run`: one normal check
- `report`: rebuilds the scoreboard page

## Not financial advice

This is a learning tool. Free signal channels are often used for pump-and-dumps and to sell
"VIP" groups. Never send money or log in to anything a channel asks you to.
