"""Generate a roast from repeated-term counts or retrieved archive excerpts.

Without a topic, try term-frequency candidates first. Otherwise retrieve
keyword/embedding hits and surrounding messages from configured home channels."""

import logging
import random
import re

from utils import chat_archive

MOMENTS = 3            # conversations handed to the model
WINDOW_BEFORE = 25
WINDOW_AFTER = 22
WINDOW_MINUTES = 45
LINE_CHARS = 110
MAX_LEN = 450          # Twitch's own limit is 500; this is a safety cap only


def home_channels():
    """Return comedy channels, falling back to analysis channels."""
    import config
    return (getattr(config, "COMEDY_CHANNELS", None)
            or getattr(config, "ANALYSIS_CHANNELS", None) or [])


# ------------------------------- retrieval --------------------------------

def _window(msg_id, channel, canon, display):
    """Format neighboring messages with the target named and others labeled someone.

    Return (text, target_line_count) when minimum coverage checks pass, else None."""
    try:
        rows = chat_archive.context_window(
            msg_id, channel, before=WINDOW_BEFORE, after=WINDOW_AFTER,
            within_minutes=WINDOW_MINUTES)
    except Exception as e:
        logging.debug(f"ragebait window failed for {msg_id}: {e!r}")
        return None
    lines, theirs, others = [], 0, 0
    for _row_id, author, content in rows:
        body = " ".join((content or "").split())
        if not body:
            continue
        if len(body) > LINE_CHARS:
            body = body[:LINE_CHARS - 1] + "…"
        if chat_archive.normalize_author(author) == canon:
            lines.append(f"{display}: {body}")
            theirs += 1
        else:
            lines.append(f"someone: {body}")
            others += 1
    if len(lines) >= 6 and theirs >= 2 and others >= 1:
        return "\n".join(lines), theirs
    return None


def _semantic_ids(canon, topic, want=6):
    """Embedding retrieval: their messages nearest in MEANING to the topic.
    The index stores text, not ids, so each hit is looked up to get the row
    it came from (which is what lets us show the surrounding conversation)."""
    try:
        from utils import persona_msg_index
        if not persona_msg_index.available(canon):
            return []
        hits = persona_msg_index.semantic_hits(canon, topic, k=want)
    except Exception as e:
        logging.debug(f"ragebait semantic retrieval skipped: {e!r}")
        return []
    out = []
    for _score, text in hits:
        row = chat_archive.message_row_for(canon, text, channels=home_channels())
        if row:
            out.append(row)
    return out


def _keyword_ids(canon, topic, want=20):
    hits = chat_archive.search_author_hits(canon, topic, limit=want)
    home = {chat_archive.normalize_channel(c) for c in home_channels()}
    return [(i, ts, ch) for i, ts, ch, _c in hits
            if not home or chat_archive.normalize_channel(ch) in home]


def moments(canon, display, topic=None, n=MOMENTS):
    """Candidate conversations, best first.

    'Best' = the one the target actually took part in most, since a
    conversation where they said two things gives nothing to work with. Only
    ONE is used per bait: handing over three at once made the model blur
    topics and people together."""
    seeds = []
    if topic:
        seeds = _semantic_ids(canon, topic) + _keyword_ids(canon, topic)
    if not seeds:
        seeds = [(i, ts, ch) for i, ts, ch, _c
                 in chat_archive.random_messages(canon, n=16,
                                                 channels=home_channels())]
    scored, seen = [], set()
    for msg_id, sent_at, channel in seeds:
        if len(scored) >= n * 3:
            break
        if msg_id in seen:
            continue
        seen.add(msg_id)
        got = _window(msg_id, channel, canon, display)
        if got:
            window, theirs = got
            scored.append((theirs, window))
    scored.sort(key=lambda s: -s[0])
    return [w for _t, w in scored[:n]]


# -------------------------------- prompt ----------------------------------

def obsession_prompt(display, found):
    """Build a roast prompt from repeated terms, counts, days, ratios and examples."""
    lines = []
    for i, o in enumerate(found, 1):
        ex = " | ".join(f'"{e}"' for e in o["examples"][:3])
        lines.append(
            f'{i}. "{o["term"]}" - in {o["count"]} of their messages across '
            f'{o["days"]} different days, about {o["ratio"]:g}x the '
            f'configured corpus-average per-message frequency.\n   they say things like: {ex}')
    return (
        "You're in a Twitch chat where close friends roast each other "
        f"constantly. Write ONE message winding up @{display}.\n\n"
        f"These terms occur more often in @{display}'s sampled archive messages "
        "than in the configured corpus overall:\n\n" + "\n".join(lines) + "\n\n"
        "Pick the ONE that's a real subject they're obsessed with - a game, "
        "a person, a hobby, a thing they clearly care about - and that you "
        "actually understand. If a word is just a typo or filler, or you "
        "can't tell what it means, skip it; do NOT mock a word you'd have to "
        "admit you don't understand. If none of them is a real subject you "
        "get, reply with only the word SKIP.\n\n"
        "Then mock them for caring about that thing SO much. The joke is "
        "about the obsession itself - what it says about them that this is "
        "what fills their chat. Riff on what the thing IS.\n\n"
        "What tends to land:\n"
        "- Do NOT recite the statistics. 'you've said X in 75 messages across "
        "27 days' is boring and robotic. The count is just how you KNOW "
        "they're obsessed - show that you know, don't read out the number.\n"
        "- Put the funniest bit at the END. Don't state a verdict up front "
        "and then explain it.\n"
        "- Be specific to THEM. Anything you could say to any chatter is dead.\n"
        "- Type like a chatter: lowercase, contractions, talk TO them. Under "
        "30 words. No hashtags, no emojis, no emote names.\n\n"
        "Nothing sincere, no slurs, no threats, nothing about death, illness "
        "or grief. Reply with ONLY the message text."
    )


def prompt_for(display, logs, topic=None):
    """One prompt. Everything here is guidance for the model to weigh, not a
    rule enforced afterwards in code."""
    topic_line = (f"\nChat asked for bait about: {topic}. Keep it about that "
                  "if the logs support it.\n" if topic else "")
    return (
        "You're in a Twitch chat where close friends roast each other "
        f"constantly. Write ONE message winding up @{display}.\n\n"
        f"Here are archive excerpts of @{display} in this chat. Their own lines "
        f"are labeled {display}; other speakers are labeled someone:\n\n" + "\n\n".join(logs) + "\n"
        f"{topic_line}\n"
        "Read the logs and find the thing worth mocking - an argument they "
        "lost, a take nobody agreed with, something they won't shut up about, "
        "a promise they never kept, a habit that's obviously theirs. Then "
        "write the wind-up.\n\n"
        "What tends to land, for you to weigh:\n"
        "- Specific beats generic. It should be something only THIS person "
        "could be accused of; anything that could be said to any chatter is "
        "dead on arrival.\n"
        "- Put the funniest or most unexpected bit at the END. Don't state a "
        "verdict and then explain it.\n"
        "- Quoting their exact words is devastating, because they can't deny "
        "it. Inventing a quote or a number is worthless for the same reason; "
        "they'll just say they never said that. Only quote and only cite "
        "numbers you can actually see in the logs above.\n"
        "- Whoever reads this wasn't in that conversation and won't remember "
        "it, so say enough inside the message that it makes sense on its own.\n"
        "- Ways people build these: quote them then react flat; compare them "
        "to a specific person doing an unrelated job; state their position "
        "neutrally then collapse it in the last few words; draw an absurdly "
        "big conclusion from something trivial; congratulate them for "
        "something that isn't an achievement; worry about them like a "
        "relative; include yourself in the insult.\n"
        "- Type like a chatter: lowercase, contractions, fragments, talk TO "
        "them. No hashtags, no emojis, no emote names. Under 40 words.\n\n"
        "Nothing sincere, no slurs, no threats, and never joke about someone "
        "dying, illness or grief. If the logs have nothing worth mocking, "
        "reply with only the word SKIP.\n"
        "Reply with ONLY the message text."
    )


def tidy(raw, display):
    """Cosmetic only: whitespace, wrapper quotes, lead with the mention."""
    text = " ".join((raw or "").split())
    text = re.sub(r'^(here.{0,20}:|message:|reply:)\s*', "", text, flags=re.I)
    if len(text) > 1 and text[0] in "\"'" and text[-1] == text[0]:
        text = text[1:-1].strip()
    d = re.escape(display)
    # drop a redundant vocative so we can re-lead cleanly: a leading "@bob,"
    # or a "filler filler @bob," near the front. Never a possessive "@bob's"
    # (the negative lookahead is what stops the orphaned-'s bug).
    text = re.sub(rf"^((?:\w+\s+){{1,3}})@?{d}(?![’'\w])[,:]\s+", r"\1", text, flags=re.I)
    text = re.sub(rf"^@?{d}(?![’'\w])[,:]?\s+", "", text, flags=re.I)
    # any remaining @mention of the target becomes the bare name: avoids a
    # double ping and the possessive-orphan bug when it's mid-sentence
    text = re.sub(rf"@{d}\b", display, text, flags=re.I)
    return f"@{display} {text}".strip()[:MAX_LEN]


# -------------------------------- command ---------------------------------

async def generate(user, channel=None, topic=None) -> str:
    from services import llm
    canon = chat_archive.normalize_author(user)
    display = chat_archive.display_name(canon)
    topic = " ".join((topic or "").split()) or None

    # Without a topic, try repeated-term candidates before archive excerpts.
    logs, source = [], "obsession"
    if not topic:
        from utils import obsessions
        try:
            found = obsessions.for_user(canon)
        except Exception as e:
            logging.warning(f"obsession mining failed for {canon}: {e!r}")
            found = []
        if found:
            prompt = obsession_prompt(display, found[:8])
            logs = [f'{o["term"]} ({o["count"]}x/{o["days"]}d)' for o in found[:8]]
    if not logs:
        source = "conversation"
        logs = moments(canon, display, topic)[:1]
        if not logs:
            where = f' about "{topic[:40]}"' if topic else ""
            return (f"@{display} nothing archived{where} in these chats worth "
                    "roasting. imagine being that forgettable")
        prompt = prompt_for(display, logs, topic)

    for _ in range(2):
        try:
            raw = await llm.chat(
                [{"role": "user", "content": prompt}],
                max_tokens=120, temperature=0.95,
            )
        except Exception as e:
            logging.warning(f"ragebait model call failed for {canon}: {e!r}")
            return llm.failure_message("ragebait")
        if not raw:
            return llm.failure_message("ragebait")
        text = tidy(raw, display)
        body = re.sub(r"@\w+", "", text).strip()
        if body and not re.fullmatch(r"skip[.!]?", body, re.I):
            remember(channel, {"target": display, "text": text, "topic": topic,
                               "logs": logs, "source": source})
            return text
        random.shuffle(logs)
    return "couldn't find anything worth roasting in there. run it again."


# ---------------------------- ~ragebait ref -------------------------------

_recent = {}
RECENT_MAX = 8


def remember(channel, entry):
    key = chat_archive.normalize_channel(channel or "")
    bucket = _recent.setdefault(key, [])
    bucket.insert(0, entry)
    del bucket[RECENT_MAX:]


def reference(channel, n=1):
    """What the nth-most-recent bait in this channel was working from."""
    key = chat_archive.normalize_channel(channel or "")
    bucket = _recent.get(key) or []
    if not bucket:
        return None
    n = max(1, min(int(n), len(bucket)))
    e = bucket[n - 1]
    label = f"bait #{n} on {e['target']}"
    if e.get("topic"):
        label += f" (topic: {e['topic'][:40]})"
    if e.get("source") == "obsession":
        return f"{label} came from what they say most: {', '.join(e.get('logs', [])[:6])}"
    theirs = [l for log in e.get("logs", []) for l in log.split("\n")
              if l.startswith(f"{e['target']}:")]
    if not theirs:
        return f"{label}: no log lines recorded"
    shown = " / ".join(t.split(": ", 1)[-1] for t in theirs[:2])
    return f'{label} came from their lines: "{shown[:200]}"'
