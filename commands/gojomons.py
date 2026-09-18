import config
from auth import is_super_admin

description = (
    "~gojomons - post the project-site link in this chat (super admins). "
    "The URL comes from config [announce] site_url."
)


async def handle_gojomons(bot, message, params):
    if not message.author or not is_super_admin(message.author.name):
        return
    url = config.ANNOUNCE_SITE_URL
    if not url:
        await message.channel.send("no site_url configured under [announce].")
        return
    await message.channel.send(url)
