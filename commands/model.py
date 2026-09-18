from auth import is_super_admin
from services import model_queue

description = (
    "Control local-AI/GPU work and inspect its queue (super admins). "
    "Off blocks persona, generation, and live embedding calls; archive and "
    "other local commands keep working.\n"
    "  ~model [status|off|on|clear]"
)


def _state_text(state: str, kind: str = "model") -> str:
    return {
        "up": f"{kind} ready",
        "busy": f"{kind} busy or loading",
        "offline": "LM Studio server offline",
        "model_missing": f"{kind} not loaded",
        "unconfigured": f"{kind} not configured",
        "disabled": "disabled",
    }.get(state, state)


async def _readiness_text() -> str:
    chat = await model_queue.server_state("chat", force=True)
    if chat == "offline":
        return _state_text(chat, "chat model")
    bits = [_state_text(chat, "chat model")]
    from config import LLM_EMBED_MODEL
    if LLM_EMBED_MODEL:
        embedding = await model_queue.server_state("embedding", force=True)
        bits.append(_state_text(embedding, "embedding model"))
    else:
        bits.append("embeddings disabled in config")
    return " | ".join(bits)


async def handle_model(bot, message, params):
    if not message.author or not is_super_admin(message.author.name):
        return
    action = params[0].lower() if params else "status"

    if action in {"off", "disable", "disabled"}:
        model_queue.set_enabled(False)
        cleared = model_queue.clear_pending()
        bits = ["local AI: disabled"]
        if cleared:
            bits.append(f"{cleared} queued command{'s' if cleared != 1 else ''} cleared")
        if model_queue.running_ticket():
            bits.append("current command will finish")
        await message.channel.send(" | ".join(bits))
        return

    if action in {"on", "enable", "enabled"}:
        model_queue.set_enabled(True)
        await message.channel.send(f"local AI: enabled | {await _readiness_text()}")
        return

    if action in {"clear", "flush", "cancel"}:
        cleared = model_queue.clear_pending()
        running = " | current command will finish" if model_queue.running_ticket() else ""
        await message.channel.send(f"local AI queue: {cleared} pending cleared{running}")
        return

    if action != "status":
        await message.channel.send("Usage: ~model [status|off|on|clear]")
        return

    if not model_queue.enabled():
        await message.channel.send(model_queue.status())
        return
    await message.channel.send(
        f"local AI: enabled | {await _readiness_text()} | {model_queue.status()}"
    )
