"""7TV emote-set editing: add / remove / search / alias.

Auth is the seventv-auth bearer token in gitignored config ([seventv] token).
The token owner must be an editor of the set being changed. Verified working
2026-07-30 (v3 GraphQL, ChangeEmoteInSet round-trip). All mutations are real
and immediate - callers gate destructive ones behind confirmation.
"""

import base64
import json
import logging
import re
import time
import urllib.request

import config

GQL = "https://7tv.io/v3/gql"
_ID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")   # 7TV object id (ULID-ish)

_CHANGE = (
    "mutation Change($id: ObjectID!, $action: ListItemAction!, "
    "$emote_id: ObjectID!, $name: String) {"
    " emoteSet(id: $id) { emotes(id: $emote_id, action: $action, name: $name)"
    " { id name } } }")
_SEARCH = (
    "query Search($query: String!, $limit: Int!) {"
    " emotes(query: $query, page: 1, limit: $limit,"
    " filter: {case_sensitive: false, exact_match: false}) {"
    " items { id name channels(page: 1, limit: 1) { total } } } }")


def enabled() -> bool:
    return bool(config.SEVENTV_TOKEN)


def token_days_left():
    try:
        p = config.SEVENTV_TOKEN.split(".")[1]
        p += "=" * (-len(p) % 4)
        exp = json.loads(base64.urlsafe_b64decode(p))["exp"]
        return (exp - time.time()) / 86400
    except Exception:
        return None


def _gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(GQL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + config.SEVENTV_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"7TV HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
    if data.get("errors"):
        raise RuntimeError("7TV: " + "; ".join(
            e.get("message", "?") for e in data["errors"])[:200])
    return data.get("data") or {}


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "nlc-seventv"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def set_id_for_room(room_id):
    """The channel's active 7TV emote-set id, or the configured default."""
    if room_id:
        try:
            u = _get_json(f"https://7tv.io/v3/users/twitch/{room_id}")
            sid = ((u or {}).get("emote_set") or {}).get("id")
            if sid:
                return sid
        except Exception as e:
            logging.debug(f"7TV set-for-room failed: {e!r}")
    return config.SEVENTV_EMOTE_SET or None


def set_emotes(set_id):
    """{name: id} for the set (name is the in-set alias)."""
    data = _get_json(f"https://7tv.io/v3/emote-sets/{set_id}")
    return {e["name"]: e["id"] for e in data.get("emotes") or []}


def search(query, limit=12):
    """[(id, name, channels), ...] best matches, ranked like the 7TV site and
    PotatBotat: exact-name matches first, then the MOST-USED version (channel
    count) - so `add BigIron` adds the popular BigIron, not a dead fork."""
    items = (_gql(_SEARCH, {"query": query, "limit": limit})
             .get("emotes") or {}).get("items") or []
    q = query.lower()
    hits = [(e["id"], e["name"], (e.get("channels") or {}).get("total") or 0)
            for e in items]
    hits.sort(key=lambda h: (h[1].lower() != q,
                             not h[1].lower().startswith(q),
                             -h[2]))
    return hits


def rename(set_id, emote_id, new_name):
    _gql(_CHANGE, {"id": set_id, "action": "UPDATE",
                   "emote_id": emote_id, "name": new_name})


def parse_ref(ref):
    """An emote id from a raw id or a 7tv.app/emotes/<id> link, else None."""
    m = _ID.search(ref or "")
    return m.group(0) if m else None


def emote_name(emote_id):
    """The emote's default/canonical name, for confirmations after adding by
    id. None on failure."""
    try:
        return _get_json(f"https://7tv.io/v3/emotes/{emote_id}").get("name")
    except Exception:
        return None


def add(set_id, emote_id, alias=None):
    _gql(_CHANGE, {"id": set_id, "action": "ADD",
                   "emote_id": emote_id, "name": alias})


def remove(set_id, emote_id):
    _gql(_CHANGE, {"id": set_id, "action": "REMOVE", "emote_id": emote_id})
