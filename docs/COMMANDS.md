# NoLifeChatter Command Bible

This is the public, source-of-truth command map for the live bot. Commands are
auto-discovered from `commands/*.py`: if a file defines `handle_name`, then
the matching prefixed chat command exists.

For compact chat help, use `~help`, `~help <category>`, or `~help <command>`.
Every command also accepts a lone `help` argument (`~askchat help`,
`~mimic help`, etc.); both forms return the same command description.
`~help ai` shows which commands can make a live local-AI/GPU call.

## Quick Index

### Translation And Language

| Command | Access | What it does |
| --- | --- | --- |
| `~autotl` | admin | Toggle auto-translation for your own messages. |
| `~setlang <LANG>` | admin | Set your translation target language, such as `EN` or `ES`. |
| `~tloutput local|whisper|channel <name>` | admin | Choose where translations are sent. |
| `~chan_autotl <channel> on|off` | super admin | Enable or disable auto-translation for one channel. |
| `~global_autotl on|off` | super admin | Global auto-translation switch. |
| `~notranslate <user> [undo]` | super admin | Stop auto-translating a specific user (they write slang the detector misreads); `undo` re-enables; no arg lists opted-out users. |
| `~practice on <learn_langs_csv> [native]` | anyone | Practice mode: translate your native language into study languages and your study-language attempts back to native. |
| `~practice off` / `~practice show` | anyone | Stop or inspect practice mode. |
| `~romanize on|off|show` | anyone | Toggle romanized readings for supported non-Latin scripts. |
| `~speak <lang>` / `~speak <lang> off` / `~speak show` | anyone | Tell the bot which language(s) you speak so short messages are handled better. |

### Archive Search And Stats

| Command | Access | What it does |
| --- | --- | --- |
| `~said <user> [chat=<channel>] [sort=] <phrase>` | anyone | Search whether a user said a phrase. Exact match first, then normalized close match. Results shuffled by default; `sort=chrono\|newest\|name` to order them. |
| `~said anyone [chat=<channel>] [sort=] <phrase>` | anyone | Search the whole archive for a phrase. Same `sort=` flag; default is a seeded shuffle. |
| `~saidnext` | anyone | Continue your last `~said` search for about a minute, keeping the same order (the shuffle seed is remembered). |
| `~saidmost <phrase> [chat=<channel>] [n]` | anyone | Who has said a phrase the most - ranks chatters by how many of their messages contain it (aliases merged, bots skipped). |
| `~regex <user|anyone> <pattern>` | anyone | Case-insensitive regex search over archived messages. |
| `~userregex <pattern> [chat=<channel>]` | anyone | Regex-search archived usernames. |
| `~quote <user>` | anyone | Post a random real quote from a user. |
| `~random <word> [user=] [chat=]` | anyone | A random real quote containing a word/phrase. Anyone by default; narrow with user= and/or chat=. |
| `~firstseen <user>` | anyone | Show a user's first archived message. |
| `~chatstats <user> [chat=<channel>]` | anyone | Show message count, first/last seen, average length, and busiest hour. |
| `~regulars [channel] [min_messages] [limit]` | anyone | Top regulars in a channel, ignoring obvious bots by default. |
| `~askchat [raw] [user=<name>\|<name>] [chat=<channel>] <question>` | anyone | Evidence-backed archive/lore QA. Normal mode fuses keyword/dense retrieval, adds safe chronological context, and asks the local LLM for a cautious cited answer; `raw` returns receipts only. |

### Persona And Generation

| Command | Access | What it does |
| --- | --- | --- |
| `~markov <user>` | anyone | Generate a local Markov-chain line from that chatter's messages. |
| `~mimic <user>` | anyone | Alias-style Markov persona command; same family as `~markov`. |
| `~persona <user> [message] [model=llama|lora]` | anyone | Ask the local LLM to reply as a chatter using archive evidence and live context. |
| `~pers <user> [message]` | anyone | Alias of `~persona` (unlisted in `~help`). |
| `~hyper <user> [message] [model=llama|lora]` | anyone | Same as `~persona`, but exaggerated for comedy. |
| `~generate <tags...>` | anyone | Generate an example message from a recipe: users, traits, topic words, `chat=`, `year=`, `engine=markov|llm`, `model=...`. |
| `~generate save <name> <tags...>` | anyone | Save a per-user generation recipe. |
| `~generate <name> [more tags]` | anyone | Use a saved recipe and optionally stack more tags. |
| `~generate list` / `~generate del <name>` | anyone | List or delete your saved recipes. |
| `~botpersona status [chat=<channel>]` | super admin | Inspect the resident persona for a channel. |
| `~botpersona off [chat=<channel>]` | super admin | Clear the resident persona for a channel. |
| `~botpersona <user> [chat=<channel>] [minutes=360] [mode=regular\|response\|random\|silent] [chance=] [topic=] [curve=] [directed=] [directed_cooldown=] [idle=]` | super admin | Set a channel-scoped resident persona that can autonomously reply and idle-chat. |
| `~botmode regular\|response\|random\|silent [minutes] [chat=<channel>]` | super admin | Change resident persona response mode and optional expiry. |
| `~botcontext [chat=<channel>] <text\|clear>` | super admin | Set extra standing instruction for the resident persona. |
| `~botchance <base> [directed] [chat=<channel>] [topic=] [idle=] [greeting=] [cooldown=]` | super admin | Tune resident persona reaction, topic-boost, idle, greeting, and cooldown probabilities. |

Important distinction: `~persona`, `~hyper`, and `~generate` are one-shot
commands. The resident persona commands above are channel-scoped and
super-admin-only.

Local-model-heavy commands share one global queue across channels. Commands
such as `~persona`, `~hyper`, LLM `~generate`, dynamic `~top`/`~bottom`,
`~axis`, uncached/`words`-mode `~why`, and `~irony` answer one at a time. The
first cold use of built-in
`~traits`/`~distinct` also queues while its axes load; warm and cached-axis
variants stay fast, as do raw/receipts-only paths. `~askchat` and emote
explainers perform their local evidence pass first; optional model synthesis
runs only when the model lane is idle, otherwise they return the local result.

### Stylometry, Similarity, Traits

| Command | Access | What it does |
| --- | --- | --- |
| `~whosaid <sentence>` | anyone | Guess who in the current chatroom is most likely to have said a line. |
| `~whosaid anyone <sentence>` | anyone | Guess against the configured analysis cohort. |
| `~markers <user> [chat=all|<channel>] [year=YYYY]` | anyone | Show distinctive words and word-pairs for a chatter. |
| `~like <user> [chat=all|<channel>] [year=YYYY]` | anyone | Lexical/emote voice neighbors with shared-marker evidence. Useful for alt-hunting. |
| `~vibes <user>` | anyone | Semantic embedding-space neighbors: same topics/energy even without shared catchphrases. |
| `~twin <user>` | anyone | Overall nearest match, blending lexical and semantic similarity. |
| `~traits <user>` | anyone | Project a chatter onto built-in trait axes relative to the room average. ⚡ marks an axis where their messages span both poles, not one side. |
| `~style <user>` | anyone | How a chatter TYPES - standout behaviors vs the room (emote rate, verbosity, caps, @mentions, profanity, vocabulary). Data-driven "structural" personality; unlike ~traits it doesn't touch the topic embedder. |
| `~top <trait> [n] [burst]` | anyone | Trait leaderboard. Built-in traits answer instantly; new words build dynamic axes. The trait may be more than one word (`~top anal lover`). For one person's rank, σ, and neighbours use an explicit `@user` or `user=<name>` - bare words are always read as the trait, never a username. |
| `~bottom <trait> [n] [burst]` | anyone | Reverse leaderboard - who leans LEAST toward a trait (most toward its opposite). Trait may be multi-word. |
| `~distinct [top\|bottom] [n]` | anyone | Chatters farthest from or closest to the room average across built-in trait axes. |
| `~why <user> <trait> [words]` | anyone | Show real indexed messages that drive a user's score and the resolved axis basis/pole. `~why emote <emote> [raw]` explains learned emote meaning; `raw` shows vector receipts. |
| `~axis <trait> [n]` | anyone | Inspect a trait/custom axis by showing nearest neighboring axes. |
| `~emote <emote> [raw]` | anyone | Explain what the bot thinks an emote means in one readable sentence; `raw` shows registry, sampled usage-vector contexts, neighbors, and cached axis scores. |
| `~explain emote <emote> [raw]` | anyone | Same emote meaning explainer, routed through the general `~explain` command. |
| `~irony [user=<name>] [chat=here\|all] <message>` | anyone | Experimental intent read combining surface wording, community repetition, unusual literal claims, and confirmed user-history agreement/conflict. |
| `~funny <user>` | anyone | Comedy-influence score from new laughers in the ~30s after a setup versus before it. Rapid same-author fragments are one setup; self/bot/noise reactions are excluded; cross-chat breadth counts each laugher once. |
| `~funny top [n]` / `~funny bottom [n]` | anyone | Funniest / least-funny chatters by comedy influence across the configured chats. |
| `~ragebait <user> [topic]` | anyone | Wind a chatter up with receipts from their own archive - a freshly LLM-composed jab built on a real conversation they took part in (home chats only) or a standing habit. Add a topic (`~ragebait bob twin primes`) to aim it at what they have said about that subject. Two-step: the model first states what actually happened, then mocks that in one sentence. Guards reject fabricated quotes and jokes that lean on context the reader cannot see. |
| `~ragebait ref [n]` | anyone | Show what the last ragebait in this chat riffed on (`n=2` for the one before). Instant - no model call. |

The analysis commands are exploratory. They are useful for debugging and fun
comparisons, not clinical or total-person labels.

### Moderation And Utility

| Command | Access | What it does |
| --- | --- | --- |
| `~help [page\|archive\|personas\|analysis\|translation\|utility\|ai\|command]` | anyone | List grouped pages, browse one category, show local-AI use, or show one command. `~mimic`/`~markov` work but are unlisted; admin commands are listed only via `~admin`. |
| `~admin` | anyone | List the admin / super-admin commands (kept out of the public `~help`; the commands still enforce their own permissions). |
| `~experimental` | anyone | List prototype/evidence commands such as `~askchat`, `~emote`, `~why emote`, and `~irony`, with hints for raw receipts mode. |
| `~ping` | anyone | Latency and host stats. |
| `~leastused [n] [months]` | anyone | Least-used 7TV emotes in the channel, counted honestly: one use per message (spam counts once), deduped across log sources, and normalized by how long each emote has existed. `~leastused most [n]` for most used. Read-only. |
| `~emotes add|remove|alias|prune ...` | editors / super admin | Edit the channel's 7TV emote set. `add <name|7tv-link> [as <alias>]` adds the most-used matching emote; `remove <name>`; `alias <name> <newname>` renames one; `replace <name> <new-name|link>` swaps one keeping the name. Trusted `[seventv] editors` do these one at a time (rate-limited); `prune <n> [months]` (super admin) previews the n least-used and needs `yes`. Needs a 7TV editor token in config. |
| `~artifacts` | anyone | Compact status for generated persona artifacts and stale semantic caches. |
| `~banuser <name>` | super admin | Ban a chatter from using bot commands. Translation/archive capture are unaffected. |
| `~banuser list` | super admin | Show command-banned users. |
| `~unbanuser <name>` | super admin | Remove a command ban. |
| `~warnings [n]` | super admin | Review recent anti-spam cooldown offenses (the escalating cooldowns described below). |
| `~model [status\|off\|on\|clear]` | super admin | Disable/enable every live local-AI call or inspect/clear its queue. Disabling clears pending work; a command already running finishes. `[llm] enabled = false` sets the startup default. `~modelqueue` remains an unlisted alias. |
| `~announce [now [chat]]` | super admin | Status of the periodic promo/reminder posts, or post immediately. Channels/message/cadence come from config `[announce]`: at most `max_per_day` posts per rolling 24h, at least `min_gap_hours` apart, randomized past that and only into an active chat. An empty `channels` list disables periodic posting. |
| `~gojomons` | super admin | Post the project-site link (config `[announce] site_url`) in the chat it's called in. |
| `~axismerge <canonical> <dup> [flip]` | super admin | Fold a duplicate dynamic trait axis into another (`flip` when `<dup>` is the opposite pole); `~axismerge del <axis>` deletes a junk axis outright; `~axismerge list` inspects saved axes. Dedup is manual on purpose - embedding cosine can't reliably tell synonyms from distinct concepts. |

Anti-spam cooldown (`command_processor` via `utils/cooldowns.py`): using
commands and waiting for each reply never costs anything. Sending a third
extra command while your previous one is still running is a breach. The first
breach gets a warning and the command is skipped. Another breach within 15
minutes puts you on a per-user cooldown: 3 minutes the first time, doubling per
repeat offense, capped at 15 minutes. While on cooldown your commands are
ignored silently after one notice. Strikes are forgiven after two quiet hours.
Every real cooldown is recorded in the settings database for `~warnings`.

## Resident Scope

The current resident layer supports one real chatter persona per channel, topic
affinity boosting from archive hits, rare idle messages, and Twitch reply-thread
responses when a triggering message ID is available. Full `~generate` recipes
as resident personas are still future work.

## Artifact Dependencies

Some commands read live SQLite tables only; others need offline artifacts:

| Artifact | Built by | Used by |
| --- | --- | --- |
| `data/unsynced/chat_archive.db` | live capture and `tools/archive/ingest_chatterino.py` | archive, stats, Markov, persona evidence |
| `data/unsynced/persona_classifier.pkl` | `tools/build/train_classifier.py` | `~whosaid`, `~markers`, `~like`, persona eval pieces |
| `data/unsynced/persona_embeddings.pkl` | `tools/build/build_persona_embeddings.py` | `~vibes`, `~twin`, trait averages |
| `data/unsynced/msg_index/` | `tools/build/build_message_index.py` | `~why`, burst `~top`, semantic persona retrieval |
| `data/unsynced/fact_bank.jsonl` | `tools/build/build_fact_bank.py` | `~askchat`, offline archive/lore QA |
| `data/unsynced/user_profiles.json` | `tools/build/build_user_profiles.py` | confirmed persona facts, `~askchat`, irony history checks |
| `data/unsynced/emote_semantics.pkl` + `data/unsynced/emote_tag_vecs.pkl` | `tools/build/build_emote_semantics.py` + emote tag-vector tooling | `~emote`, `~explain emote`, `~why emote` |

Use `~artifacts` or `python tools/check/artifact_status.py` to check whether these
artifacts are missing, missing build metadata, or built with the current
semantic unit/model.

After identity merges, embedding-model changes, or major filter changes, run
`scripts/windows/10-rebuild-persona-artifacts.bat` or `tools/build/rebuild_persona_artifacts.py`.
For an unattended run, use `scripts/windows/10-rebuild-persona-artifacts-background.bat`; it
writes stdout/stderr logs under `data/unsynced`.
The default semantic unit for embeddings/indexes is now a merged utterance; use
`--semantic-unit message` only for a deliberate A/B against the old behavior.
