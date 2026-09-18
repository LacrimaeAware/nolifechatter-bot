"""Honest 7TV emote usage for a channel - shared by tools/archive/emote_usage.py
and the ~leastused command.

Better than a rolling-window bot count:
- usage = DISTINCT archived messages containing the emote (spamming it 50x in
  one message counts once)
- rows deduped first (the archive triple-stores messages across log sources)
- lifetime-aware: each emote's 7TV add-date clamps its window and ranking is
  uses-per-day-AVAILABLE, so a month-old emote isn't punished for being new
- bots, bot commands, and 7TV add/remove system lines don't count
"""

import glob
import json
import logging
import os
import re
import time
import urllib.request

import config
from utils import chat_archive

_RENAME = re.compile(r"renamed 7TV emote (\S+) to (\S+?)[.\s]*$")
_rename_cache = {}   # channel -> (newest_log_mtime, {current_name: [names]})

BOTS = {
    "streamelements", "nightbot", "fossabot", "moobot", "wizebot",
    "soundalerts", "streamlabs", "pokemoncommunitygame", "potatbotat",
    "buttsbot", "supibot", "automod", "mtgbot", "thepositivebot",
}
# The operator's own bot account and community-specific bots come from
# [persona] exclude_users in config.toml, so no account name is hard-coded.
BOTS |= {str(u).lower() for u in getattr(config, "EXCLUDE_USERS", set())}
_SYSTEM = re.compile(
    r"(added|removed|renamed) \d* ?7TV emotes?|channel emotes reloaded|"
    r"has been (timed out|banned)", re.I)

_MONTH = 30.44 * 86400
_cache = {}   # (channel, months) -> (built_at, ranked_rows)
CACHE_TTL = 6 * 3600


def _get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "nlc-emote-usage"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def seven_tv_set(*, set_id=None, room_id=None):
    """{emote_name: added_epoch} for a 7TV set, resolved from an explicit set
    id or a Twitch room id. Empty dict on any failure."""
    try:
        if not set_id and room_id:
            user = _get_json(f"https://7tv.io/v3/users/twitch/{room_id}")
            set_id = ((user or {}).get("emote_set") or {}).get("id")
        if not set_id:
            return {}
        data = _get_json(f"https://7tv.io/v3/emote-sets/{set_id}")
        return {e["name"]: (e.get("timestamp") or 0) / 1000.0
                for e in data.get("emotes") or [] if e.get("name")}
    except Exception as e:
        logging.warning(f"7TV set fetch failed (set={set_id} room={room_id}): {e!r}")
        return {}


def rename_history(channel):
    """{current_name: [every name this emote has been known by]} for the
    channel, parsed from local Chatterino logs (the only place 7TV rename
    events are recorded). Cached until the newest log file changes. Empty when
    the logs aren't on this machine - counting then just uses current names."""
    base = config.CHATTERINO_LOG_BASE
    d = os.path.join(base, chat_archive.normalize_channel(channel)) if base else ""
    files = sorted(glob.glob(os.path.join(d, "*.log"))) if d and os.path.isdir(d) else []
    if not files:
        return {}
    newest = max((os.path.getmtime(f) for f in files), default=0)
    cached = _rename_cache.get(channel)
    if cached and cached[0] == newest:
        return cached[1]

    # Replay renames in chronological order (filenames are date-sorted). Each
    # "OLD to NEW" moves the accumulated name-history from OLD onto NEW, so a
    # chain would->Would->WoULD collapses onto the final current name.
    hist = {}
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = _RENAME.search(line)
                    if not m:
                        continue
                    old, new = m.group(1), m.group(2)
                    names = hist.pop(old, [old])
                    if new not in names:
                        names.append(new)
                    hist[new] = names
        except Exception as e:
            logging.debug(f"rename-history read failed for {f}: {e!r}")
    _rename_cache[channel] = (newest, hist)
    return hist


def _count(channel, emotes, since_epoch):
    cutoff = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(since_epoch))
    rows = chat_archive.connect().execute(
        "SELECT author, sent_at, content FROM messages "
        "WHERE channel = ? AND sent_at >= ?",
        (chat_archive.normalize_channel(channel), cutoff)).fetchall()
    counts = {name: 0 for name in emotes}
    seen = {}
    for author, sent_at, content in rows:
        text = " ".join((content or "").split())
        if not text:
            continue
        who = chat_archive.normalize_author(author)
        if who in BOTS or who.endswith("bot") or text[0] in "~$#!+%&<":
            continue
        if _SYSTEM.search(text):
            continue
        try:
            t = time.mktime(time.strptime(sent_at, "%Y-%m-%d %H:%M:%S"))
        except Exception:
            continue
        key = (who, re.sub(r"[^a-zA-Z0-9 ]", "", text)[:120])
        if key in seen and t - seen[key] < 90:     # triple-stored line
            continue
        seen[key] = t
        for token in set(text.split()):
            if token in counts:
                counts[token] += 1
    return counts


def rank(channel, emotes, months=6, min_days=7):
    """[(per_week, uses, days_available, added_epoch, name)] worst-first, over
    the last `months`, skipping emotes younger than `min_days`. Rename-aware:
    an emote's uses include every name it's been known by (so renaming a
    popular emote doesn't make it look dead and prunable)."""
    now = time.time()
    window_start = now - months * _MONTH
    hist = rename_history(channel)
    # count every current name PLUS every historical alias of a current emote
    to_count = dict.fromkeys(emotes, 0)
    for name in emotes:
        for alt in hist.get(name, ()):
            to_count.setdefault(alt, 0)
    counts = _count(channel, to_count, window_start)
    out = []
    for name, added in emotes.items():
        start = max(window_start, added or window_start)
        days = (now - start) / 86400
        if days < min_days:
            continue
        names = set(hist.get(name, [name])) | {name}
        uses = sum(counts.get(n, 0) for n in names)
        out.append((uses / days * 7, uses, days, added, name))
    out.sort(key=lambda s: (s[0], s[1]))
    return out


def ranked_cached(channel, *, set_id=None, room_id=None, months=6):
    key = (chat_archive.normalize_channel(channel), months)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    emotes = seven_tv_set(set_id=set_id, room_id=room_id)
    if not emotes:
        return None
    rows = rank(channel, emotes, months=months)
    _cache[key] = (time.time(), rows)
    return rows
