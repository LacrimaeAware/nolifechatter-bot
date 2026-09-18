"""What a chatter will not shut up about - measured, not guessed.

Built for ~ragebait after every "hand the model a random conversation and
ask it to find something funny" approach failed: most chat contains nothing
mockable, so a weak model invents a joke out of noise. An obsession is
different - it is a fact the archive can prove (N messages across M separate
days, X times the rest of the chat's rate), it needs no surrounding
conversation to make sense, and it leaves the model only the phrasing.

Measured over the two home chats: 25-60 usable obsessions per chatter, and
unlike dunk/argument mining it works for quiet chatters too.
"""

import json
import logging
import os
import re
import time
from collections import Counter, defaultdict

from utils import chat_archive

CACHE_FILE = os.path.join("data", "unsynced", "obsession_df_v2.json")
MIN_MESSAGES = 12       # times they've brought it up
MIN_DAYS = 8            # ...across this many separate days (not one binge)
MIN_RATIO = 5.0         # ...at this multiple of everyone else's rate
MIN_OTHERS = 6          # ...and this many DISTINCT people must use it too
EXAMPLES = 5

_word = re.compile(r"[a-z][a-z0-9'’-]{2,}")
_cache = {}             # canon -> (built_at, [obsession, ...])

# words that are common everywhere and say nothing about a person
_STOP = set("""
the and you your that this have has had for but not with from they them their
was were are its it's what when where who why how all any some one two too
very much more most just like about into over back down here there then than
than only ever never still even also because could would should will can did
does doing done get gets got getting make makes made take takes went come
comes going gonna wanna kinda sorta yeah yep nah lol lmao idk imo tbh btw
know knows knew think thinks thought say says said see saw seen look looks
want wants need needs really actually literally probably maybe sure right
good bad nice cool great best worse worst thing things stuff shit fuck fucking
guy guys man dude bro people someone everyone something anything nothing
time times day days week month year years today tomorrow yesterday now
""".split())


def _emotes():
    try:
        from utils import emote_meaning
        return {e.lower() for e in emote_meaning.registry()}
    except Exception as e:
        logging.debug(f"obsessions: emote registry unavailable: {e!r}")
        return set()


def _home():
    from utils import ragebait
    return [chat_archive.normalize_channel(c) for c in ragebait.home_channels()]


def _corpus_df(force=False):
    """{term: [messages, distinct_people]} across the home chats, cached.

    Two baselines, both needed. `messages` says how common the word is, so a
    person's rate can be compared against it. `distinct_people` is what
    separates a SUBJECT from a personal typo: several people talk about osrs,
    but only one person types 'tihnk'. Both are computed on DEDUPED rows
    the archive stores most messages 2-3 times (chatterino/zonian/live logs
    overlap), which otherwise inflates every count and makes a typo look
    like other people were using it too.
    """
    if not force and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as fh:
                blob = json.load(fh)
            if blob.get("total"):
                return blob["df"], blob["total"]
        except Exception as e:
            logging.warning(f"obsessions: cache unreadable, rebuilding: {e!r}")
    home = _home()
    placeholders, params = chat_archive._in_clause(home) if home else ("", [])
    where = f"WHERE channel IN ({placeholders})" if home else ""
    counts, people, total = Counter(), defaultdict(set), 0
    seen = set()
    conn = chat_archive.connect()
    for author, content in conn.execute(
            f"SELECT author, content FROM messages {where}", params):
        low = " ".join((content or "").split()).lower()
        if not low:
            continue
        who = chat_archive.normalize_author(author)
        key = (who, re.sub(r"[^a-z0-9 ]", "", low)[:120])
        if key in seen:               # same line from a second log source
            continue
        seen.add(key)
        terms = set(_word.findall(low))
        if not terms:
            continue
        total += 1
        counts.update(terms)
        for t in terms:
            if len(people[t]) < 64:   # bounded; we only need "several"
                people[t].add(who)
    df = {t: [c, len(people[t])] for t, c in counts.items() if c >= 3}
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"df": df, "total": total, "built": time.time()}, fh)
    except Exception as e:
        logging.warning(f"obsessions: could not cache df: {e!r}")
    return df, total


def _their_messages(canon):
    home = _home()
    keys = chat_archive.author_keys(canon)
    author_ph, author_params = chat_archive._in_clause(keys)
    chan_sql, chan_params = "", []
    if home:
        ph, chan_params = chat_archive._in_clause(home)
        chan_sql = f"AND channel IN ({ph}) "
    return chat_archive.connect().execute(
        f"SELECT sent_at, content FROM messages WHERE author IN ({author_ph}) "
        f"{chan_sql}",
        [*author_params, *chan_params],
    ).fetchall()


def for_user(canon, limit=12, force=False):
    """[{term, count, days, ratio, examples}] - their standing obsessions,
    strongest first. Cached in memory for the process lifetime."""
    canon = chat_archive.normalize_author(canon)
    if not force and canon in _cache:
        return _cache[canon][1]

    df, corpus_total = _corpus_df()
    rows = _their_messages(canon)
    if not rows or corpus_total <= 0:
        return []

    emotes = _emotes()
    counts, days, samples = Counter(), defaultdict(set), defaultdict(list)
    mine_total = 0
    seen_lines = set()
    for sent_at, content in rows:
        text = " ".join((content or "").split())
        low = text.lower()
        if not text or text.lstrip()[:1] in "~$!<+%&#/":     # bot commands
            continue
        key = re.sub(r"[^a-z0-9 ]", "", low)[:120]
        if key in seen_lines:            # archive stores some lines 2-3x
            continue
        seen_lines.add(key)
        mine_total += 1
        day = (sent_at or "")[:10]
        for term in set(_word.findall(low)):
            if term in _STOP or term in emotes or len(term) < 3:
                continue
            counts[term] += 1
            days[term].add(day)
            if len(samples[term]) < 12 and 4 <= len(text.split()) <= 40:
                samples[term].append(text)

    out = []
    for term, n in counts.most_common(600):
        if n < MIN_MESSAGES or len(days[term]) < MIN_DAYS:
            continue
        # A SUBJECT is something several people talk about - just less often
        # than this person. A personal typo or speech tic ('tihnk', 'wuld',
        # 'aswell') scores an identical rate-ratio but essentially nobody
        # else types it. That is what separates "won't shut up about osrs"
        # from "spells think wrong", and the latter is not a joke.
        df_count, df_people = df.get(term, [0, 0])
        if df_people < MIN_OTHERS:
            continue
        theirs = n / mine_total
        base = (df_count or 1) / corpus_total
        ratio = theirs / base if base else 0.0
        if ratio < MIN_RATIO or not samples[term]:
            continue
        out.append({
            "term": term,
            "count": n,
            "days": len(days[term]),
            "ratio": round(ratio, 1),
            "examples": samples[term][:EXAMPLES],
        })
    out.sort(key=lambda o: -(o["ratio"] * min(o["count"], 200)))
    out = out[:limit]
    _cache[canon] = (time.time(), out)
    return out


def pick(canon, topic=None):
    """One obsession to mock. With a topic, the closest match to it."""
    found = for_user(canon)
    if not found:
        return None
    if topic:
        want = {w for w in _word.findall(topic.lower()) if w not in _STOP}
        if want:
            scored = [(len(want & ({o["term"]} | set(
                _word.findall(" ".join(o["examples"]).lower())))), o)
                for o in found]
            scored.sort(key=lambda s: -s[0])
            if scored and scored[0][0]:
                return scored[0][1]
    return found[0] if len(found) == 1 else __import__("random").choice(found[:8])
