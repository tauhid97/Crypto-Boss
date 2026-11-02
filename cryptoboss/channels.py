"""READER - reads public Telegram channels (their free web page t.me/s/<name>, no login) and
pulls trade calls out of the posts.

Posts are just text from strangers. We only pull numbers out of them; nothing in a post can
make the bot do anything else.
"""
import html
import re

import requests

NUM = r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([kK])?\s*\$?"
COIN_PATTERNS = [r"Instrument:\s*([A-Z0-9]+?)USDT", r"#([A-Z0-9]{2,12}?)(?:/?USDT)?\b", r"\$([A-Z]{2,10})\b"]
SKIP = r"achieved|✅|profit in \d"          # brag posts about old calls, not new calls


def _num(m, i=1):
    x = float(m.group(i).replace(",", ""))
    return x * 1000 if m.group(i + 1) else x


def parse(text):
    """One post -> {coin, side, entry, stop, target} or None if it isn't a clear trade call."""
    if re.search(SKIP, text, re.I):
        return None
    coin = next((m.group(1) for p in COIN_PATTERNS if (m := re.search(p, text))), None)
    e = re.search(r"Entry(?:\s*price|\s*zone)?\s*[:\-]?\s*" + NUM + r"(?:\s*(?:-|–|to)\s*" + NUM + ")?", text, re.I)
    s = re.search(r"(?:Stop[\s-]*loss|Stoploss|Stop|\bSL\b)\s*[:\-]?\s*" + NUM, text, re.I)
    t = re.search(r"(?:Targets?|\bTP\s*1?|Take[\s-]*profit\s*1?)\s*[:\-]?\s*" + NUM, text, re.I)
    if not (coin and e and s and t):
        return None
    entry = _num(e)
    if e.group(3):                                  # an entry zone like "14.10 - 13.90" -> the middle
        entry = (entry + _num(e, 3)) / 2
    stop, target = _num(s), _num(t)
    if stop < entry < target:
        side = "long"
    elif stop > entry > target:
        side = "short"
    else:
        return None
    return {"coin": coin.upper(), "side": side, "entry": entry, "stop": stop, "target": target}


def fetch_posts(channel):
    """The latest ~20 posts on a public channel: [{id, text}], oldest first."""
    r = requests.get(f"https://t.me/s/{channel}", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    out = []
    for blk in re.split(r'(?=<div class="tgme_widget_message_wrap)', r.text):
        pid = re.search(r'data-post="[^/"]+/(\d+)"', blk)
        txt = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', blk, re.S)
        if pid and txt:
            t = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", txt.group(1))))
            out.append({"id": int(pid.group(1)), "text": t})
    return sorted(out, key=lambda p: p["id"])
