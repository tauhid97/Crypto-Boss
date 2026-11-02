"""SCOREBOARD - builds docs/index.html, the public track-record page (every signal, win or lose)."""
import html
import os

import pandas as pd

from . import config as C
from .skills import money


def _pct(x):
    return f"{x:+.2f}%" if x is not None and x == x else "-"


def _channel_rows(calls):
    from .checker import channel_stats
    out = ""
    for s in channel_stats(calls):
        win = f"{s['win']:.0f}%" if s["win"] is not None else "-"
        ch = html.escape(s["channel"])
        out += (f"<tr><td><a href='https://t.me/s/{ch}'>@{ch}</a></td><td>{s['calls']}</td><td>{s['graded']}</td>"
                f"<td>{win}</td><td>{_pct(s['avg'])}</td><td>{_pct(s['total'])}</td><td>{s['rh_calls']}</td>"
                f"<td>{_pct(s['rh_avg'])}</td></tr>")
    return out or "<tr><td colspan='8'>No calls seen yet. Watching...</td></tr>"


def build(df, calls=None):
    if calls is None:
        from .checker import load_calls
        calls = load_calls()
    channel_rows = _channel_rows(calls)
    traded = df[df["status"].isin(["target", "stop", "timeout"])]
    if len(traded):
        stats = (f"{len(traded)} trades &middot; win {100 * (traded['r_multiple'] > 0).mean():.0f}% &middot; "
                 f"avg {traded['r_multiple'].mean():+.2f}R &middot; total {traded['r_multiple'].sum():+.1f}R")
    else:
        stats = "No finished trades yet."
    by_skill = ""
    for skill, g in traded.groupby("skill"):
        by_skill += (f"<tr><td>{html.escape(skill)}</td><td>{len(g)}</td>"
                     f"<td>{100 * (g['r_multiple'] > 0).mean():.0f}%</td><td>{g['r_multiple'].sum():+.1f}R</td></tr>")
    rows = ""
    for _, s in df.sort_values("published_at", ascending=False).head(200).iterrows():
        t = pd.Timestamp(s["published_at"]).tz_convert(C.TIMEZONE)
        r = s["r_multiple"]
        r_txt = f"{r:+.2f}R" if s["status"] in ("target", "stop", "timeout") else ""
        cls = "win" if r_txt and r > 0 else "loss" if r_txt else ""
        rows += (f"<tr><td>{t:%b %d %I:%M %p}</td><td>{html.escape(s['coin'])}</td><td>{html.escape(s['skill'])}</td>"
                 f"<td>{money(s['entry'])}</td><td>{money(s['stop'])}</td><td>{money(s['target'])}</td>"
                 f"<td>{s['status']}</td><td class='{cls}'>{r_txt}</td></tr>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Crypto Boss Scoreboard</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#666;--line:#e5e5e5;--win:#0a7d38;--loss:#b3261e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--muted:#999;--line:#333;--win:#4cc27a;--loss:#ff6b60}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:900px;padding:16px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{border-bottom:1px solid var(--line);padding:6px 4px;text-align:left}}
.wrap{{overflow-x:auto}} .win{{color:var(--win)}} .loss{{color:var(--loss)}} .muted{{color:var(--muted)}}
</style></head><body>
<h1>Crypto Boss Scoreboard</h1>
<h2>Signal Checker: free channels, graded</h2>
<p class="muted">Every trade call these public channels post, graded from the moment we first saw it. No leverage,
only the first target counts, Robinhood's spread taken off. "RH buys" = buy calls on coins Robinhood sells.</p>
<div class="wrap"><table><tr><th>Channel</th><th>Calls</th><th>Graded</th><th>Win</th><th>Avg</th><th>Total</th>
<th>RH buys</th><th>RH avg</th></tr>{channel_rows}</table></div>
<h2>Quick trades (switched off)</h2>
<p><b>{C.MODE}</b> &middot; {stats}</p>
<p class="muted">Every signal, win or lose. Robinhood's spread (about {C.SPREAD_PCT * 200:.1f}% per trade) is already taken off.
R = what we risked: +2R means we won twice what we risked. Updated {pd.Timestamp.now(tz=C.TIMEZONE):%b %d %I:%M %p} ET.</p>
<h2>By skill</h2><div class="wrap"><table><tr><th>Skill</th><th>Trades</th><th>Win</th><th>Total</th></tr>{by_skill}</table></div>
<h2>Every signal</h2><div class="wrap"><table><tr><th>Sent (ET)</th><th>Coin</th><th>Skill</th><th>Entry</th><th>Stop</th>
<th>Target</th><th>Result</th><th>R</th></tr>{rows}</table></div>
<p class="muted">Practice signals for learning only, not financial advice. Crypto is very risky.</p>
</body></html>"""
    os.makedirs(os.path.dirname(C.REPORT_FILE), exist_ok=True)
    open(C.REPORT_FILE, "w").write(page)
