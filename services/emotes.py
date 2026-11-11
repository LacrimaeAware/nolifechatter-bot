"""Cached per-channel 7TV, BTTV and FFZ emote names for preprocessing.

Names are fetched by Twitch room id in a background thread. The lookup
returns an empty set until loading finishes.
"""

import asyncio
import logging

import requests

_cache: dict[str, set[str]] = {}   # room_id -> emote names
_fetching: set[str] = set()


def _safe_json(url: str, timeout: int = 8):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logging.debug(f"Emote fetch failed for {url}: {e}")
    return None


def _fetch_emote_names(room_id: str) -> set[str]:
    names: set[str] = set()

    j = _safe_json(f"https://7tv.io/v3/users/twitch/{room_id}")
    if j:
        for e in (j.get("emote_set") or {}).get("emotes") or []:
            if e.get("name"):
                names.add(e["name"])

    j = _safe_json("https://7tv.io/v3/emote-sets/global")
    if j:
        for e in j.get("emotes") or []:
            if e.get("name"):
                names.add(e["name"])

    j = _safe_json(f"https://api.betterttv.net/3/cached/users/twitch/{room_id}")
    if j:
        for e in (j.get("channelEmotes") or []) + (j.get("sharedEmotes") or []):
            if e.get("code"):
                names.add(e["code"])

    j = _safe_json("https://api.betterttv.net/3/cached/emotes/global")
    if j:
        for e in j or []:
            if e.get("code"):
                names.add(e["code"])

    j = _safe_json(f"https://api.frankerfacez.com/v1/room/id/{room_id}")
    if j:
        for s in (j.get("sets") or {}).values():
            for e in s.get("emoticons") or []:
                if e.get("name"):
                    names.add(e["name"])

    return names


async def _load(room_id: str) -> None:
    try:
        _cache[room_id] = await asyncio.to_thread(_fetch_emote_names, room_id)
        logging.info(f"Loaded {len(_cache[room_id])} emotes for channel id {room_id}")
    except Exception as e:
        logging.warning(f"Emote load failed for {room_id}: {e}")
        _cache[room_id] = set()
    finally:
        _fetching.discard(room_id)


def ensure_channel_emotes(room_id: str | None) -> set[str]:
    """Return cached emote names for a channel, kicking off a background fetch
    the first time. Returns an empty set until the fetch completes."""
    if not room_id:
        return set()
    if room_id in _cache:
        return _cache[room_id]
    if room_id not in _fetching:
        _fetching.add(room_id)
        asyncio.create_task(_load(room_id))
    return set()


def strip_emotes(text: str, emote_names: set[str]) -> str:
    """Remove whitespace-separated tokens matching known emote names."""
    if not text or not emote_names:
        return text
    return " ".join(t for t in text.split() if t not in emote_names)
