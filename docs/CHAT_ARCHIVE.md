# Chat archive

The archive stores imported Chatterino logs and messages from the bot's joined
channels in one SQLite database. Search, statistics and message generation
read from this database.

Use `tools/archive/ingest_chatterino.py` to import logs and
`tools/archive/ask_archive.py` to search from a terminal. In Twitch chat, use
`~said`, `~quote`, `~firstseen` and `~chatstats`. The
[architecture guide](ARCHITECTURE.md) lists the implementation files.

## Storage and search

Phrase searches use SQLite's [FTS5](https://www.sqlite.org/fts5.html) full-text
index through Python's `sqlite3` module. They do not need a model server.
Commands such as `~askchat` can pass retrieved messages to a local model to
answer a question.

Allow disk space for both the database and its full-text index. Use
`--channels` to limit the import.

## Sources

### 1. Chatterino2 logs (historical, one-time ingest)

Chatterino logs live under `<Chatterino2>/Logs/Twitch/Channels/`, one
subdirectory per channel, one file per channel per day, named
`<channel>-YYYY-MM-DD.log`. Expected format:

- **Encoding:** UTF-8 without BOM, bare `\n` line endings (even on Windows).
  Real emoji and arbitrary bytes appear - open with `encoding="utf-8",
  errors="replace"`.
- **Header lines:** `# Start logging at 2025-03-06 14:37:36 Eastern Standard Time`
  and a matching `# Stop logging at ...`. These repeat **mid-file** every time
  Chatterino restarts or the tab reopens, and Stop is often missing after
  crashes. Treat any line starting with `# ` as a header.
- **Chat lines:** `[HH:MM:SS] username: message text` - 24-hour **local** time,
  time-only. The *date comes from the filename*; the timezone only from the
  header text. Twitch logins are `[a-z0-9_]+`, so splitting on the **first**
  `": "` after the timestamp separates the username from the message. Message
  bodies can contain colons, so do not split on the last one.
- **System lines:** timestamped but with no `user:` part - `connected`,
  `disconnected`, `joined channel`, emote-reload notices, etc. A chat-line
  regex like `^\[(\d{2}:\d{2}:\d{2})\] ([a-z0-9_]+): (.*)$` must be allowed to
  fail and fall through to a system branch.
- **Moderation lines:** `user has been timed out for 1m. ` (note trailing
  space + period), bans, unbans. Moderator actions can look like
  chat lines - `[12:10:48] somemod: somemod timed out someuser for 7d. ` parses
  as a "message" from the moderator. Filter lines whose body matches the
  moderation-notice shapes before analysing chat messages.
- **Empty lines:** `[21:56:54] ` (timestamp + single space) occur; skip their
  empty content.
- Messages are always single-line (one IRC message = one log line); no `/me`
  marker survives into the log.
- Channel directories accumulate typo/rename duplicates of the same streamer
  over time - keep an optional alias map to merge them at ingest.
- Sibling log streams exist next to `Channels/`: `Mentions/`, `Whispers/`,
  `AutoMod/`, `Live/` (stream up/down events - handy as an activity index).
  Ingest is per-stream optional.

### 2. Live capture (ongoing)

When live capture is enabled, `handlers.process_message` inserts messages
from joined channels into the same table. Chatterino does not need to be running.

### 3. Other log sources

Any log that can be converted to the Chatterino layout above (one directory per
channel, `<channel>-YYYY-MM-DD.log`, `[HH:MM:SS] login: text` lines) can be
ingested with the same tool. Rows carry a `source` column so imports from a
mirror can be told apart from Chatterino history and live capture. Imported
one-speaker files are not complete transcripts: `chat_archive.context_window()`
returns only the hit itself for author-only neighborhoods, so conversation
reconstruction never treats adjacent rows from such a file as surrounding chat.

## Schema

```sql
CREATE TABLE messages (
    id       INTEGER PRIMARY KEY,
    channel  TEXT NOT NULL,        -- lowercase channel login
    author   TEXT NOT NULL,        -- canonical lowercase user login
    sent_at  TEXT NOT NULL,        -- 'YYYY-MM-DD HH:MM:SS' (local time)
    content  TEXT NOT NULL,
    source   TEXT NOT NULL DEFAULT 'chatterino',  -- 'chatterino' | 'live' | 'zonian'
    src_path TEXT, -- originating log file; re-ingest of a grown file replaces
                   -- exactly its own rows (alias-merged channels stay intact)
    raw_author TEXT -- login before alias normalization
);
CREATE INDEX idx_msg_author  ON messages(author, sent_at);
CREATE INDEX idx_msg_channel ON messages(channel, sent_at);

-- External-content full-text index keyed to messages.id.
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content, content='messages', content_rowid='id'
);

-- Ingest ledger so re-running the importer is incremental and idempotent.
CREATE TABLE ingested_files (
    path  TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    rows  INTEGER NOT NULL
);

-- ID/display cache. Offline lookup time is deliberately separate from real
-- live activity so maintenance order cannot make an old alias the display name.
CREATE TABLE author_ids (
    author         TEXT PRIMARY KEY,
    twitch_id      TEXT,
    checked_at     TEXT,
    display        TEXT,
    last_seen_live TEXT
);
```

Schema changes are additive migrations in `chat_archive.connect()`. Alias maps
are also fingerprinted into generated semantic/persona artifacts; changing an
identity map makes artifact status warn until those files are rebuilt.

Semantic utterance v3 merges a person's short message bursts independently in
each channel and collapses duplicate text components inside the merged text.
Source message IDs and parts preserve the chronology. Generated message
indexes and person vectors record the utterance version; older versions
produce an artifact warning.

Chatterino imports and live capture can overlap on the import day. The schema
above does not enforce `UNIQUE(channel, author, sent_at, content)` across
sources.

The database is stored at `data/unsynced/chat_archive.db`.

## Ingest CLI

```
python tools/archive/ingest_chatterino.py <logs-root> [--channels a,b,c] [--since 2025-01-01]
```

- Walks `<logs-root>/<channel>/<channel>-YYYY-MM-DD.log`, skips files already
  in `ingested_files` with unchanged mtime. Imports new files and reimports
  changed files.
- Parses per the format spec above; system/moderation/header/empty lines are
  counted but not stored.
- Batched inserts with `executemany`, in one transaction per file.

## Query layer

Offline (full archive):

```
python tools/archive/ask_archive.py said <user> <phrase...>    # did X ever say Y -> matching rows
python tools/archive/ask_archive.py near <user> <phrase...>    # closest normalized lines by X
python tools/archive/ask_archive.py quote <user>               # random quote by X
python tools/archive/ask_archive.py stats <user>               # count, first/last seen, busiest hour
python tools/archive/ask_archive.py search <phrase...>         # phrase search, all authors
```

Phrases are matched as whole-word exact phrases (FTS5 under the hood, with the
input always quoted - chat text can't inject query syntax). A phrase with no
alphanumeric characters at all (emoji-only) falls back to substring search,
since the tokenizer would otherwise drop it.

In Twitch chat:

| Command | Does |
| --- | --- |
| `~said <user> <phrase>` | exact quote search first; if none, closest normalized match |
| `~quote <user>` | random real quote from the archive |
| `~firstseen <user>` | first recorded message + date |
| `~chatstats <user>` | message count, top emotes, busiest hour |

Query the FTS table with `CROSS JOIN messages` (or
an `IN (SELECT rowid ...)` subquery) so SQLite runs the FTS match once and
probes by rowid. A plain `JOIN` can change the loop order and re-evaluate the
match for each candidate row.

When exact `said` search finds nothing, the command and CLI fall back to a
normalized close-match check. That treats straight vs curly apostrophes,
punctuation, case, and spacing as irrelevant, so copied lines are still caught
when chat/LLM output changes typography or adds a small mention/emote tail.
Use `tools/archive/ask_archive.py near <user> <line>` when you explicitly want the
closest lines instead of an exact-first answer.

## Search by meaning

The optional message index supports retrieval by similar meaning. The
[architecture guide](ARCHITECTURE.md#analysis-data-files) lists its builder,
embedding model requirements and the commands that use it. Phrase search and
normalized close matches do not require this index.
