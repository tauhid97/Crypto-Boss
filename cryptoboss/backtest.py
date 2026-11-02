"""PRACTICE ON THE PAST - replays old candles every 15 minutes with the exact same rules."""
import pandas as pd

from . import config as C
from .skills import find_new, prepare
from .tracker import settle


def run(market, days=30):
    frames = {c: prepare(df) for c, df in market.items()}
    end = max(df.index[-1] for df in frames.values())
    t = end - pd.Timedelta(days=days)
    busy_until = {}                       # coin -> time it's free for a new signal
    trades = []
    while t <= end:
        blocked = {c for c, u in busy_until.items() if u > t}
        new, _, _ = find_new(frames, t, blocked)
        for s in new:
            s.update(published_at=t.isoformat(), status="pending")
            r = settle(s, frames[s["coin"]], end + pd.Timedelta(C.CANDLE))
            trades.append(r)
            free = pd.Timestamp(r["exit_time"]) if r.get("exit_time") else end
            busy_until[s["coin"]] = max(free, t + pd.Timedelta(C.COOLDOWN))
        t += pd.Timedelta(C.CANDLE)
    df = pd.DataFrame(trades)
    lines = [f"Backtest: last {days} days, every 15 minutes, spread included (hypothetical)."]
    if not len(df):
        return df, "\n".join(lines + ["No trades."])
    done = df[df["status"].isin(["target", "stop", "timeout"])]
    lines.append(f"{len(df)} signals, {len(done)} trades bought, "
                 f"{(df['status'] == 'no_fill').sum()} never bought.")
    for skill, g in done.groupby("skill"):
        lines.append(f"- {skill}: {len(g)} trades, win {100 * (g['r_multiple'] > 0).mean():.0f}%, "
                     f"avg {g['r_multiple'].mean():+.2f}R, total {g['r_multiple'].sum():+.1f}R")
    if len(done):
        lines.append(f"All: avg {done['r_multiple'].mean():+.2f}R per trade, total {done['r_multiple'].sum():+.1f}R")
    return df, "\n".join(lines)
