"""Occasional per-channel promo/reminder posts with jittered timing.

Cadence contract: at most ANNOUNCE_MAX_PER_DAY posts per rolling 24h per
channel, never sooner than ANNOUNCE_MIN_GAP_HOURS after that channel's last
post - and past that eligibility the actual moment is random (a per-check
probability that ramps the longer it's been) and prefers an ACTIVE chat, so
the schedule breathes instead of metronoming every 12 hours and the link
lands when people are actually around to see it.

State (last post times per channel) persists in data/unsynced so the
keep-alive loop's restarts don't reset the clock.
"""

import asyncio
import json
import logging
import os
import random
import time

import config
from utils import chat_archive

STATE_FILE = os.path.join("data", "unsynced", "announcer_state.json")
CHECK_SECONDS = 300


def _load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            state = json.load(fh)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _save_state(state: dict):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception as e:
        logging.error(f"announcer state save failed: {e!r}")


def message_text() -> str:
    return " ".join(part for part in (config.ANNOUNCE_MESSAGE, config.ANNOUNCE_URL)
                    if part).strip()


def enabled() -> bool:
    return bool(config.ANNOUNCE_CHANNELS) and bool(message_text())


def posts_in_last_day(state: dict, channel: str, now: float = None) -> list:
    now = now or time.time()
    return [t for t in state.get(channel, []) if now - t < 24 * 3600]


def hours_since_last(state: dict, channel: str, now: float = None) -> float:
    now = now or time.time()
    stamps = state.get(channel, [])
    return (now - max(stamps)) / 3600 if stamps else float("inf")


def post_chance(hours: float) -> float:
    """Per-check (5 min) post probability once past the minimum gap.

    Ramps 2% -> 10% between min_gap and 2*min_gap, so the post lands a
    randomized few hours after eligibility: typically ~2/day when chat is
    around, sometimes 1 - never a fixed every-12-hours metronome."""
    gap = max(0.1, config.ANNOUNCE_MIN_GAP_HOURS)
    if hours < gap:
        return 0.0
    ramp = min(1.0, (hours - gap) / gap)
    return 0.02 + 0.08 * ramp


def _activity_ok(channel: str) -> bool:
    """At least N archived messages in this channel in the last window
    don't announce into a dead chat. Archive unavailable -> allow (fall back
    to the time gates alone rather than never posting)."""
    need = config.ANNOUNCE_ACTIVITY_MIN_MESSAGES
    if need <= 0:
        return True
    try:
        cutoff = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(time.time() - config.ANNOUNCE_ACTIVITY_WINDOW_MIN * 60))
        row = chat_archive.connect().execute(
            "SELECT COUNT(*) FROM messages WHERE channel = ? AND sent_at >= ?",
            (chat_archive.normalize_channel(channel), cutoff)).fetchone()
        return (row[0] if row else 0) >= need
    except Exception as e:
        logging.debug(f"announcer activity check failed for {channel}: {e!r}")
        return True


def due(state: dict, channel: str, now: float = None, rand=random.random) -> bool:
    now = now or time.time()
    if len(posts_in_last_day(state, channel, now)) >= config.ANNOUNCE_MAX_PER_DAY:
        return False
    hours = hours_since_last(state, channel, now)
    chance = post_chance(hours)
    if chance <= 0.0:
        return False
    # starvation valve: after 3x the minimum gap (a full day+ of silence from
    # the announcer) stop waiting for a busy room - a quiet day must delay
    # posts, not zero them out
    starving = hours > 3 * max(0.1, config.ANNOUNCE_MIN_GAP_HOURS)
    if not starving and not _activity_ok(channel):
        return False
    return rand() < chance


def record_post(state: dict, channel: str, now: float = None):
    now = now or time.time()
    state.setdefault(channel, []).append(now)
    state[channel] = state[channel][-10:]
    _save_state(state)


def status_lines() -> list:
    """Compact per-channel status for the ~announce admin command."""
    state = _load_state()
    out = []
    for name in config.ANNOUNCE_CHANNELS:
        recent = len(posts_in_last_day(state, name))
        hours = hours_since_last(state, name)
        since = "never" if hours == float("inf") else f"{hours:.1f}h ago"
        gate = "capped" if recent >= config.ANNOUNCE_MAX_PER_DAY else (
            "waiting (min gap)" if post_chance(hours) <= 0 else "eligible")
        out.append(f"#{name}: last {since}, {recent}/{config.ANNOUNCE_MAX_PER_DAY} today, {gate}")
    return out


async def post_now(bot, channel_name: str) -> str:
    """Immediate post (admin/test path). Records the post so cadence holds."""
    text = message_text()
    if not text:
        return "announcer has no message/url configured"
    channel = bot.get_channel(channel_name)
    if not channel:
        return f"not joined to #{channel_name}"
    await channel.send(text)
    record_post(_load_state(), channel_name)
    return f"posted to #{channel_name}"


async def loop(bot):
    """Background cadence loop; started from event_ready when configured."""
    logging.info(f"announcer active for {len(config.ANNOUNCE_CHANNELS)} channel(s)")
    while True:
        await asyncio.sleep(CHECK_SECONDS)
        try:
            if not enabled():
                continue
            state = _load_state()
            for name in config.ANNOUNCE_CHANNELS:
                if not due(state, name):
                    continue
                channel = bot.get_channel(name)
                if not channel:
                    logging.debug(f"announcer: not joined to #{name}")
                    continue
                await channel.send(message_text())
                record_post(state, name)
                logging.info(f"announcer posted to #{name}")
        except Exception as e:
            logging.error(f"announcer loop error: {e!r}")
