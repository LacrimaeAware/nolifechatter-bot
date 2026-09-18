from auth import is_super_admin
from utils import announcer

description = (
    "~announce - status of the periodic promo/reminder posts (super admins). "
    "~announce now [chat] posts immediately (counts toward the daily cap). "
    "Channels/message/cadence live in config [announce]; at most max_per_day "
    "posts per rolling 24h, min_gap_hours apart, randomized and "
    "activity-aware past that."
)


async def handle_announce(bot, message, params):
    if not message.author or not is_super_admin(message.author.name):
        return
    if not announcer.enabled():
        await message.channel.send(
            "announcer off - set [announce] channels + message/url in config.")
        return
    if params and params[0].lower() in ("now", "post", "send"):
        import config
        target = (params[1].lstrip("#").lower() if len(params) > 1
                  else config.ANNOUNCE_CHANNELS[0])
        result = await announcer.post_now(bot, target)
        await message.channel.send(result)
        return
    await message.channel.send("announcer: " + " | ".join(announcer.status_lines()))
