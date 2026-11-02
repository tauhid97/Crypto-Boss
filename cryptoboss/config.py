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

# The quick-trades skills lost money in a 30-day replay (-0.47R a trade after the spread), so they're OFF.
# The Signal Checker is what runs. Set True only to collect practice data on the quick trades.
QUICK_TRADES = False

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
ENTRY_WINDOW = "1h"                # if the price doesn't reach the entry within 1 hour, cancel
MAX_HOLD = "4h"                    # sell after 4 hours no matter what
COOLDOWN = "2h"                    # wait 2 hours before a new signal on the same coin
MAX_NEW_PER_RUN = 2

# --- Costs ---
# Robinhood crypto has no fee but builds in a "spread": you pay a bit more to buy and get a bit less
# when you sell. We assume 0.3% each way (0.6% per round trip). Raise this if your fills look worse.
SPREAD_PCT = 0.003

# --- Messages ---
TIMEZONE = "America/New_York"
RECAP_HOUR = 21                    # send the daily recap at about 9 PM New York time
