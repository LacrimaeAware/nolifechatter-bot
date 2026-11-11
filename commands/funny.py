import asyncio

from utils import chat_archive
from utils import comedic_influence as ci

description = (
    "~funny <user> | ~funny top|bottom [n] - archive laughter index: other "
    "chatters with laughter markers after a message who were not laughing "
    "before it. Repeat responses by one chatter are downweighted. "
    "100 = baseline average. chat= overrides the chats."
)


def _parse(params):
    channels = None
    rest = []
    for p in params:
        if p.lower().startswith("chat="):
            vals = [chat_archive.normalize_channel(c)
                    for c in p.split("=", 1)[1].split(",") if c.strip()]
            channels = tuple(vals) or None
        else:
            rest.append(p)
    return channels, rest


async def handle_funny(bot, message, params):
    channels, rest = _parse(params or [])
    chans = channels or ci.DEFAULT_CHANNELS
    if not rest:
        await message.channel.send("Usage: ~funny <user> | ~funny top [n] | ~funny bottom [n]")
        return

    sub = rest[0].lower().lstrip("@")
    if sub in ("top", "bottom"):
        n = 5
        if len(rest) > 1 and rest[1].isdigit():
            n = max(1, min(int(rest[1]), 10))
        rows = await asyncio.to_thread(ci.leaderboard, chans, n, sub == "bottom")
        if not rows:
            await message.channel.send("Not enough data to rank comedy yet.")
            return
        label = "lowest comedy index" if sub == "bottom" else "highest comedy index"
        parts = [f"{i}. {chat_archive.display_name(a)} ({d['index']})"
                 for i, (a, d) in enumerate(rows, 1)]
        await message.channel.send(f"😂 {label} [{'+'.join(chans)}]: " + " · ".join(parts))
        return

    user = chat_archive.display_name(sub)
    d = await asyncio.to_thread(ci.user_score, sub, chans)
    if not d:
        await message.channel.send(
            f"Not enough data to score {user} in {'/'.join(chans)} "
            f"(needs {ci.MIN_REGULAR}+ eligible message groups and laughter "
            f"from several different chatters)."
        )
        return
    best = d.get("best_text") or ""
    tail = f" · most new laughers after: \"{best[:140]}\"" if best else ""
    await message.channel.send(
        f"😂 {user}: comedy index {d['index']} · laughter markers from {d['breadth']} "
        f"different chatters · based on {d['setups']} message groups{tail}"
    )
