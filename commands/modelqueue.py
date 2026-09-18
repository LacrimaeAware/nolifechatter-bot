from commands.model import handle_model

description = (
    "Alias of ~model for compatibility.\n"
    "  ~model [status|off|on|clear]"
)


async def handle_modelqueue(bot, message, params):
    await handle_model(bot, message, params)
