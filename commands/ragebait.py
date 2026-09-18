from utils import chat_archive, ragebait

description = (
    "~ragebait <user> [topic] - wind someone up with receipts from their own "
    "archive: a freshly LLM-composed jab built on a real conversation they "
    "were in or a standing habit. Add a topic (~ragebait bob twin primes) to "
    "aim it at what they've said about that subject. All facts are real; "
    "nothing is invented. Needs the local model. ~ragebait ref [n] shows what "
    "the last bait riffed on (n=2 is the one before that)."
)


async def handle_ragebait(bot, message, params):
    if not params:
        await message.channel.send("Usage: ~ragebait <user> | ~ragebait ref [n]")
        return
    channel = message.channel.name if message.channel else ""
    first = params[0].lower().lstrip("@")

    if first.startswith("ref"):
        n = 1
        if "=" in first:
            tail = first.split("=", 1)[1]
            n = int(tail) if tail.isdigit() else 1
        elif len(params) > 1 and params[1].isdigit():
            n = int(params[1])
        out = ragebait.reference(channel, n)
        await message.channel.send(
            out or "no ragebait to explain in this chat yet.")
        return

    target = params[0].lstrip("@")
    canon = chat_archive.normalize_author(target)
    if bot.nick and canon == chat_archive.normalize_author(bot.nick):
        caller = message.author.name if message.author else "you"
        await message.channel.send(
            f"@{caller} trying to ragebait the bait machine. adorable")
        return
    topic = " ".join(params[1:]).strip() or None
    text = await ragebait.generate(canon, channel=channel, topic=topic)
    await message.channel.send(text)
