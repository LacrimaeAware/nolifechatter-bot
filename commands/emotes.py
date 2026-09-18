import asyncio
import re
import time

import config
from auth import is_super_admin
from utils import emote_usage, seventv

description = (
    "~emotes - manage the channel's 7TV emote set. "
    "add <name|7tv-link> [as <alias>] adds the most popular matching emote; "
    "remove <name>; alias <name> <newname> renames one in the set. Trusted "
    "editors can do these one at a time (rate-limited). "
    "prune <n> [months] removes the n least-used emotes (super admins; previews "
    "first, needs 'yes')."
)

_PENDING = {}          # set_id -> (built_at, [(emote_id, name), ...])
_PENDING_TTL = 180
_LAST_EDIT = {}        # user -> epoch of last single edit


def _can_edit_one(user):
    u = (user or "").lower()
    return is_super_admin(user) or u in config.EMOTE_EDITORS


def _rate_limited(user):
    """True (blocked) if this editor edited too recently. Super admins exempt."""
    if is_super_admin(user):
        return 0
    now = time.time()
    wait = config.EMOTE_EDIT_COOLDOWN - (now - _LAST_EDIT.get(user.lower(), 0))
    return wait if wait > 0 else 0


def _mark_edit(user):
    _LAST_EDIT[user.lower()] = time.time()


def _warn():
    d = seventv.token_days_left()
    return " (⚠ 7TV token expires soon)" if d is not None and d < 2 else ""


async def handle_emotes(bot, message, params):
    user = message.author.name if message.author else ""
    if not seventv.enabled():
        if _can_edit_one(user):
            await message.channel.send("7TV editing is off - set [seventv] token in config.")
        return
    if not params:
        await message.channel.send(
            "Usage: ~emotes add <name|link> [as <alias>] | remove <name> | "
            "alias <name> <newname> | prune <n> [months] [yes]")
        return

    sub = params[0].lower()
    room_id = (getattr(message, "tags", None) or {}).get("room-id")
    channel = message.channel.name if message.channel else ""

    if sub == "prune":
        if not is_super_admin(user):
            return                      # mass removal: super admins only, silent
        set_id = await asyncio.to_thread(seventv.set_id_for_room, room_id)
        if not set_id:
            await message.channel.send("Couldn't resolve this channel's 7TV set.")
            return
        await _prune(message, channel, set_id, params[1:])
        return

    if sub not in ("add", "remove", "rm", "del", "alias", "rename", "replace", "swap"):
        await message.channel.send("Usage: ~emotes add|remove|alias|replace|prune ...")
        return

    # single-emote edits: trusted editors, rate-limited
    if not _can_edit_one(user):
        return
    wait = _rate_limited(user)
    if wait:
        await message.channel.send(f"@{user} slow down - {wait:.0f}s before your next emote edit.")
        return
    set_id = await asyncio.to_thread(seventv.set_id_for_room, room_id)
    if not set_id:
        await message.channel.send("Couldn't resolve this channel's 7TV set.")
        return

    if sub == "add":
        await _add(message, user, set_id, params[1:])
    elif sub in ("alias", "rename"):
        await _alias(message, user, set_id, params[1:])
    elif sub in ("replace", "swap"):
        await _replace(message, user, set_id, params[1:])
    else:
        await _remove(message, user, set_id, params[1:])


async def _add(message, user, set_id, args):
    if not args:
        await message.channel.send("Usage: ~emotes add <name|7tv-link> [as <alias>]")
        return
    # alias via "as X", "as:X", "as=X", or "as: X" (any casing)
    text = " ".join(args).strip()
    alias = None
    m = re.search(r"\s+as\s*[:=]?\s*(\S+)\s*$", text, re.I)
    if m:
        alias = m.group(1)
        text = text[:m.start()].strip()
    ref = text

    emote_id = seventv.parse_ref(ref)
    if not emote_id:
        hits = await asyncio.to_thread(seventv.search, ref)
        if not hits:
            await message.channel.send(f"No 7TV emote found for '{ref}'.")
            return
        emote_id = hits[0][0]
    try:
        await asyncio.to_thread(seventv.add, set_id, emote_id, alias)
    except Exception as e:
        await message.channel.send(f"Add failed: {e}")
        return
    _mark_edit(user)
    # report the actual in-set name, not the raw input
    shown = alias or await asyncio.to_thread(seventv.emote_name, emote_id) or "it"
    await message.channel.send(f"✅ added {shown} to the set{_warn()}")


async def _remove(message, user, set_id, args):
    name = " ".join(args).strip()
    if not name:
        await message.channel.send("Usage: ~emotes remove <name>")
        return
    current = await asyncio.to_thread(seventv.set_emotes, set_id)
    eid = current.get(name) or next(
        (i for n, i in current.items() if n.lower() == name.lower()), None)
    if not eid:
        await message.channel.send(f"'{name}' isn't in the set.")
        return
    try:
        await asyncio.to_thread(seventv.remove, set_id, eid)
    except Exception as e:
        await message.channel.send(f"Remove failed: {e}")
        return
    _mark_edit(user)
    await message.channel.send(f"🗑️ removed {name}{_warn()}")


async def _alias(message, user, set_id, args):
    if len(args) < 2:
        await message.channel.send("Usage: ~emotes alias <current-name> <new-name>")
        return
    old, new = args[0], args[1]
    current = await asyncio.to_thread(seventv.set_emotes, set_id)
    eid = current.get(old) or next(
        (i for n, i in current.items() if n.lower() == old.lower()), None)
    if not eid:
        await message.channel.send(f"'{old}' isn't in the set.")
        return
    try:
        await asyncio.to_thread(seventv.rename, set_id, eid, new)
    except Exception as e:
        await message.channel.send(f"Rename failed: {e}")
        return
    _mark_edit(user)
    await message.channel.send(f"✏️ {old} → {new}{_warn()}")


async def _replace(message, user, set_id, args):
    """Swap the current emote named <old> for a new one, keeping the same name.
    A set can't hold two of the same name, so this removes then adds - with a
    rollback that re-adds the old emote if the new one fails to add."""
    if len(args) < 2:
        await message.channel.send("Usage: ~emotes replace <current-name> <new-name|7tv-link>")
        return
    old = args[0]
    ref = " ".join(args[1:]).strip()
    current = await asyncio.to_thread(seventv.set_emotes, set_id)
    old_id = current.get(old) or next(
        (i for n, i in current.items() if n.lower() == old.lower()), None)
    if not old_id:
        await message.channel.send(f"'{old}' isn't in the set to replace.")
        return
    old_name = next((n for n, i in current.items() if i == old_id), old)

    new_id = seventv.parse_ref(ref)
    if not new_id:
        hits = await asyncio.to_thread(seventv.search, ref)
        if not hits:
            await message.channel.send(f"No 7TV emote found for '{ref}'.")
            return
        new_id = hits[0][0]
    if new_id == old_id:
        await message.channel.send("That's the same emote - nothing to replace.")
        return

    try:
        await asyncio.to_thread(seventv.remove, set_id, old_id)
    except Exception as e:
        await message.channel.send(f"Replace failed (couldn't remove old): {e}")
        return
    try:
        await asyncio.to_thread(seventv.add, set_id, new_id, old_name)
    except Exception as e:
        # rollback: put the original back so nothing is lost
        try:
            await asyncio.to_thread(seventv.add, set_id, old_id, old_name)
            note = " (original restored)"
        except Exception:
            note = " (⚠ original NOT restored - re-add it manually)"
        await message.channel.send(f"Replace failed adding the new emote: {e}{note}")
        return
    _mark_edit(user)
    await message.channel.send(f"🔁 replaced {old_name} with the new emote{_warn()}")


async def _prune(message, channel, set_id, args):
    lower = [a.lower() for a in args]
    confirm = "yes" in lower or "confirm" in lower
    nums = [float(a) for a in lower if a.replace(".", "").isdigit()]
    if not nums:
        await message.channel.send("Usage: ~emotes prune <n> [months] [yes]")
        return
    n = max(1, min(int(nums[0]), 50))
    months = nums[1] if len(nums) > 1 else 6

    if confirm:
        held = _PENDING.get(set_id)
        if not held or time.time() - held[0] > _PENDING_TTL or len(held[1]) != n:
            await message.channel.send(
                f"Preview expired - run '~emotes prune {n} {months:g}' again first.")
            return
        removed, failed = [], []
        for eid, name in held[1]:
            try:
                await asyncio.to_thread(seventv.remove, set_id, eid)
                removed.append(name)
            except Exception:
                failed.append(name)
        _PENDING.pop(set_id, None)
        msg = f"🗑️ removed {len(removed)} emotes: " + ", ".join(removed[:30])
        if failed:
            msg += f" | failed: {', '.join(failed[:10])}"
        await message.channel.send(msg[:480] + _warn())
        return

    ranked = await asyncio.to_thread(
        emote_usage.ranked_cached, channel, set_id=set_id, months=int(months))
    if not ranked:
        await message.channel.send("Couldn't read emote usage for this channel.")
        return
    names = await asyncio.to_thread(seventv.set_emotes, set_id)
    victims, listed = [], []
    for _rate, uses, _days, _added, name in ranked[:n]:
        eid = names.get(name)
        if eid:
            victims.append((eid, name))
            listed.append(f"{name}({uses})")
    _PENDING[set_id] = (time.time(), victims)
    await message.channel.send(
        f"would remove these {len(victims)} least-used (last {months:g}mo): "
        + ", ".join(listed)[:400]
        + f" - run '~emotes prune {n} {months:g} yes' to do it")
