import asyncio

from utils import chat_archive
from utils.persona_embeddings import available, load, neighbors

description = (
    "Closest matches in message-embedding space (topics and language). "
    "The meaning counterpart of ~like's vocabulary overlap.\n"
    "  ~vibes <user>"
)


async def handle_vibes(bot, message, params):
    if not params:
        await message.channel.send("Usage: ~vibes <user>")
        return
    user = chat_archive.normalize_author(params[0].lstrip("@"))
    if not available():
        await message.channel.send(
            "No semantic vectors built yet (run tools/build/build_persona_embeddings.py)."
        )
        return
    sims = await asyncio.to_thread(neighbors, user, n=4)
    if not sims:
        await message.channel.send(
            f"No semantic vector for {chat_archive.display_name(user)} (not in the roster yet).")
        return
    # High-similarity flag: midpoint between the stored split-half self-similarity
    # and 95th-percentile between-author score, with defaults for older artifacts.
    d = load()
    flag_at = (d.get("self_sim_ceiling", 0.82) + d.get("cross_p95", 0.52)) / 2
    parts = [f"{chat_archive.display_name(a)} ({s:.2f}{' high similarity' if s >= flag_at else ''})"
             for a, s in sims]
    await message.channel.send(
        f"🧬 {chat_archive.display_name(user)}'s closest vibes: " + " · ".join(parts))
