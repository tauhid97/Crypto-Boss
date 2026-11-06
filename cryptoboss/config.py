"""All the settings in one place. Change a number here to change how the bot behaves."""

BRAND_NAME = "Crypto Boss"
COINS_FILE = "coins.txt"
SIGNALS_FILE = "data/signals.csv"
STATE_FILE = "data/state.json"
REPORT_FILE = "docs/index.html"
CHANNELS_FILE = "channels.txt"
CALLS_FILE = "data/channel_calls.csv"
CHECKER_STATE_FILE = "data/checker_state.json"
COMMANDS_STATE_FILE = "data/commands_state.json"   # which Telegram messages from Boss were already answered

# PRACTICE until the track record has looked good for 2-3 months. There is no "live" mode yet on purpose.
MODE = "PRACTICE"

# Scalping skills run 24/7 in PRACTICE (fake money) so we can see live which ones (if any) really win.
QUICK_TRADES = True
# The Signal Checker (grading public channels) is switched off - Boss wants our own trades instead.
SIGNAL_CHECKER = False

# --- Coach: quick to bench, slow to trust ---
# BENCHED: after just 3 finished trades, if its last (up to) 10 trades average below -0.10R. It keeps
#   practicing quietly (so it can earn its way back), but its signals are no longer messaged.
# TRUSTED: its last 5 trades average above +0.10R. Its signals get the full message. (A trusted skill is
#   never benched.) Every other skill is still LEARNING: its signals come as short one-liners.
COACH_BENCH_TRADES = 3
COACH_BENCH_R = -0.10
COACH_LOOKBACK = 10
COACH_TRUST_TRADES = 5
COACH_TRUST_R = 0.10

# --- Signal Checker (grades calls from public channels) ---
CALL_ENTRY_WINDOW = "3D"           # price must reach the channel's entry within 3 days, or it's "never filled"
CALL_MAX_HOLD = "14D"              # after 14 days in the trade, sell at the price then

# --- Which coins to watch ---
CANDLE = "15min"                   # one candle = 15 minutes
WATCH_COUNT = 5                    # only the 5 wildest coins right now
MIN_24H_DOLLAR_VOL = 2_000_000     # skip coins almost nobody is trading (on Coinbase)
MARKET_COIN = "BTC"                # the Weather check watches Bitcoin
STORM_DROP_PCT = -2.0              # Bitcoin down 2%+ in the last 4 hours = stormy, no new buys

# --- Each trade ---
TARGET_R = 2.0                     # aim to win 2x what we risk
MIN_RISK_PCT = 1.0                 # stop at least 1% away, so the 2x target (2%+) beats Robinhood's spread
MAX_RISK_PCT = 6.0
MIN_TARGET_PCT = 1.2               # skip trades whose target is less than 1.2% away (the spread would eat it)
ENTRY_WINDOW = "1h"                # if the price doesn't reach the entry within 1 hour, cancel
MAX_HOLD = "4h"                    # sell after 4 hours no matter what
DAY_ENTRY_WINDOW = "4h"            # day skills (Wake-Up Rally): 4 hours to get bought
DAY_MAX_HOLD = "24h"               # ...and they may hold up to 1 day (the test needed the full day)
COOLDOWN = "2h"                    # each skill waits 2 hours before a new signal on the same coin
# More practice = faster learning: every skill may trade the same coin (one active trade per coin per skill),
# up to 3 new trades per skill per day and 30 in total per day (days start at midnight UTC).
SKILL_DAILY_CAP = 3
DAILY_CAP = 30
MAX_NEW_PER_RUN = 8

# --- Costs ---
# Robinhood crypto has no fee but builds in a "spread": you pay a bit more to buy and get a bit less
# when you sell. We assume 0.3% each way (0.6% per round trip). Raise this if your fills look worse.
SPREAD_PCT = 0.003

# --- Messages ---
TIMEZONE = "America/New_York"
RECAP_HOUR = 21                    # send the daily recap at about 9 PM New York time
