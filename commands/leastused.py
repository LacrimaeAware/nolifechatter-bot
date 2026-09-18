import asyncio

from utils import emote_usage

description = (
    "~leastused [n] [months] - least-used 7TV emotes in this channel, counted "
    "honestly: one use per message (spam counts once), deduped, and normalized "
    "by how long each emote has existed so new ones aren't unfairly buried. "
    "~leastused most [n] shows the most used. Default 5 emotes over 6 months."
)


def _parse(params):
    most = False
    nums = []
    for p in params:
        low = p.lower()
        if low in ("most", "top"):
            most = True
        elif low.replace(".", "").isdigit():
            nums.append(float(low))
    n = int(nums[0]) if nums else 5
    months = nums[1] if len(nums) > 1 else 6
    return most, max(1, min(n, 15)), max(0.5, min(months, 48))


async def handle_leastused(bot, message, params):
    most, n, months = _parse(params or [])
    room_id = (getattr(message, "tags", None) or {}).get("room-id")
    channel = message.channel.name if message.channel else ""
    if not room_id:
        await message.channel.send("Can't read this channel's 7TV set right now.")
        return

    rows = await asyncio.to_thread(
        emote_usage.ranked_cached, channel, room_id=room_id, months=int(months))
    if not rows:
        await message.channel.send(
            "No 7TV emotes found for this channel (or 7TV is unreachable).")
        return

    picked = list(reversed(rows[-n:])) if most else rows[:n]
    label = "most" if most else "least"
    parts = [f"{name} ({uses})" for _rate, uses, _days, _added, name in picked]
    await message.channel.send(
        f"📊 {label}-used 7TV emotes in #{channel} (last {months:g}mo, "
        f"uses in brackets): " + " · ".join(parts))
