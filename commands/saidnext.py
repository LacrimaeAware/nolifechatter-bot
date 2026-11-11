from commands.said import saidnext

description = (
    "Show the next page of your last ~said search. The saved search expires "
    "after 10 minutes without paging.\n"
    "  ~saidnext"
)


async def handle_saidnext(bot, message, params):
    await saidnext(bot, message)
