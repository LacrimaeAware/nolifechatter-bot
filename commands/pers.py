from commands.persona import handle_persona

description = (
    "Ask the local LLM to reply as a chatter, using archive evidence and live "
    "context.\n"
    "  ~pers <user> [message] [model=llama|lora]   alias of ~persona"
)


async def handle_pers(bot, message, params):
    await handle_persona(bot, message, params)
