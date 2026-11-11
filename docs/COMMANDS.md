# Commands

Type commands in Twitch chat with the `~` prefix. The access column shows who
can use each command; admin accounts are set in `config.toml`.

For compact chat help, use `~help`, `~help <category>`, or `~help <command>`.
Every command also accepts a lone `help` argument (`~askchat help`,
`~mimic help`, etc.); both forms return the same command description.
`~help ai` shows which commands use a local model.

## Command list

[Translation](#translation-and-languages) ·
[Chat search](#chat-search-and-statistics) ·
[Message generation](#message-generation) ·
[Chat analysis](#chat-analysis) ·
[Moderation and utilities](#moderation-and-utilities)

### Translation and languages

| Command | Access | What it does |
| --- | --- | --- |
| `~autotl` | admin | Toggle auto-translation for your own messages. |
| `~setlang <LANG>` | admin | Set your translation target language, such as `EN` or `ES`. |
| `~tloutput local\|whisper\|channel <name>` | admin | Choose where translations are sent. |
| `~chan_autotl <channel> on\|off` | super admin | Enable or disable auto-translation for one channel. |
| `~global_autotl on\|off` | super admin | Global auto-translation switch. |
| `~notranslate <user> [undo]` | super admin | Stop auto-translating a user. `undo` enables it again; no argument lists users whose messages are excluded. |
| `~practice on <learn_langs_csv> [native]` | anyone | Whisper study-language translations of your native-language messages; translate study-language messages back to native in chat. |
| `~practice off` / `~practice show` | anyone | Stop or inspect practice mode. |
| `~romanize on\|off\|show` | anyone | Toggle romanized readings for supported non-Latin scripts. |
| `~speak <lang>` / `~speak <lang> off` / `~speak show` | anyone | Tell the bot which language(s) you speak so short messages are handled better. |

### Chat search and statistics

| Command | Access | What it does |
| --- | --- | --- |
| `~said <user> [chat=<channel>] [sort=] <phrase>` | anyone | Search a user's messages for a phrase. Tries exact matches first, then normalized close matches. Results are shuffled by default; `sort=chrono\|newest\|name` changes the order. |
| `~said anyone [chat=<channel>] [sort=] <phrase>` | anyone | Search everyone's messages for a phrase. Uses the same `sort=` options; the default shuffle keeps its seed for paging. |
| `~saidnext` | anyone | Show more results from your last `~said` search, in the same order. Available for 10 minutes after the last page. |
| `~saidmost <phrase> [chat=<channel>] [n]` | anyone | Rank chatters by the number of their messages containing a phrase. Account aliases are combined and bots are excluded. |
| `~regex <user\|anyone> <pattern>` | anyone | Case-insensitive regex search over archived messages. |
| `~userregex <pattern> [chat=<channel>]` | anyone | Regex-search archived usernames. |
| `~quote <user>` | anyone | Post a random saved message from a user. |
| `~random <word> [user=] [chat=]` | anyone | Post a random saved message containing a word or phrase. Optionally limit it to a user or channel. |
| `~firstseen <user>` | anyone | Show a user's first archived message. |
| `~chatstats <user> [chat=<channel>]` | anyone | Show message count, first/last seen, average length, and busiest hour. |
| `~regulars [channel] [min_messages] [limit]` | anyone | Top regulars in a channel, ignoring obvious bots by default. |
| `~askchat [raw] [user=<name>\|<name>] [chat=<channel>] <question>` | anyone | Answer a question using messages from the archive, with citations. `raw` shows the source messages without asking a model. |

### Message generation

| Command | Access | What it does |
| --- | --- | --- |
| `~persona [model=llama\|lora] <user> [message]` | anyone | Use a local model to reply in a chatter's style, using their saved messages and the current conversation. |
| `~pers <user> [message]` | anyone | Alias of `~persona` (unlisted in `~help`). |
| `~hyper [model=llama\|lora] <user> [message]` | anyone | Like `~persona`, with an exaggerated style for comedy. |
| `~generate <tags...>` | anyone | Generate a message by combining users, traits and a topic. Supports `chat=`, `year=`, `engine=markov\|llm` and `model=...`. |
| `~generate save <name> <tags...>` | anyone | Save a per-user generation recipe. |
| `~generate <name> [more tags]` | anyone | Use a saved recipe and optionally stack more tags. |
| `~generate list` / `~generate del <name>` | anyone | List or delete your saved recipes. |
| `~botpersona status [chat=<channel>]` | super admin | Show the active persona for a channel. |
| `~botpersona off [chat=<channel>]` | super admin | Turn off the channel's active persona. |
| `~botpersona <user> [chat=<channel>] [minutes=360] [mode=regular\|response\|random\|silent] [chance=] [topic=] [curve=] [directed=] [directed_cooldown=] [idle=]` | super admin | Keep a persona active in a channel so the bot can reply to chat and post occasional messages on its own. |
| `~botmode regular\|response\|random\|silent [minutes] [chat=<channel>]` | super admin | Choose when the channel persona responds and optionally set an expiry time. |
| `~botcontext [chat=<channel>] <text\|clear>` | super admin | Set or clear extra instructions for the channel persona. |
| `~botchance <base> [directed] [chat=<channel>] [topic=] [idle=] [greeting=] [cooldown=]` | super admin | Adjust response chances, topic boosts, idle messages, greetings and cooldowns for the channel persona. |
| `~markov <user>` | anyone | Generate a message from a chatter's saved word patterns using a Markov chain. No model server needed. |
| `~mimic <user>` | anyone | Generate a Markov message from a chatter's history, like `~markov`. |

`~persona`, `~hyper` and `~generate` produce one reply. The `~botpersona`
commands keep a persona active in one channel and require super-admin access.

Commands that use a local model share one queue across channels. See
[model requests](ARCHITECTURE.md#model-requests) for which commands wait and
which can return results without a model.

### Chat analysis

| Command | Access | What it does |
| --- | --- | --- |
| `~whosaid <sentence>` | anyone | Guess who in the current chatroom is most likely to have said a line. |
| `~whosaid anyone <sentence>` | anyone | Guess which chatter in the configured analysis group is most likely to have written a line. |
| `~markers <user> [chat=all\|<channel>] [year=YYYY]` | anyone | Show distinctive words and word-pairs for a chatter. |
| `~like <user> [chat=all\|<channel>] [year=YYYY]` | anyone | Find chatters with similar word and emote use, and show the shared words behind the match. |
| `~vibes <user>` | anyone | Find chatters with similar topics and tone using message embeddings, even when they do not share catchphrases. |
| `~twin <user>` | anyone | Find the closest match by combining word-use and message-embedding similarity. |
| `~traits <user>` | anyone | Score a chatter's messages on built-in trait scales relative to the room average. ⚡ means their messages span both ends of a scale. |
| `~style <user>` | anyone | Compare a chatter's emote use, message length, caps, @mentions, profanity and vocabulary with the room average. Uses writing patterns rather than topic embeddings. |
| `~top <trait> [n] [burst]` | anyone | Rank chatters for a trait. Built-in traits use existing scales; new words create a scale. Traits can contain several words (`~top anal lover`). Use `@user` or `user=<name>` for one person's rank, σ and neighbours; bare words are read as the trait. |
| `~bottom <trait> [n] [burst]` | anyone | Rank chatters in reverse: least toward a trait and most toward its opposite. Traits can contain several words. |
| `~distinct [top\|bottom] [n]` | anyone | Show chatters farthest from or closest to the room average across built-in trait scales. |
| `~why <user> <trait> [words]` | anyone | Show the indexed messages contributing to a user's trait score and which end of the scale is used. `~why emote <emote> [raw]` explains emote meaning; `raw` shows the underlying vector comparisons. |
| `~axis <trait> [n]` | anyone | Show the nearest built-in or custom trait scales to a given trait. |
| `~emote <emote> [raw]` | anyone | Summarize an emote's inferred meaning. `raw` shows registry information, sampled usage contexts, neighbouring emotes and cached trait scores. |
| `~explain emote <emote> [raw]` | anyone | Another way to run `~emote` through the `~explain` command. |
| `~irony [user=<name>] [chat=here\|all] <message>` | anyone | Estimate whether a message is ironic using its wording, repeated phrases, unusual literal claims and agreement or conflict with the user's past messages. |
| `~funny <user>` | anyone | Score how many new people laugh in roughly 30 seconds after a message compared with before it. Rapid fragments by one author count as one setup; self, bot and noise reactions are excluded, and each laugher counts once across chats. |
| `~funny top [n]` / `~funny bottom [n]` | anyone | Rank chatters from highest or lowest `~funny` score across the configured chats. |
| `~ragebait <user> [topic]` | anyone | Generate a one-sentence jab about a chatter, using a conversation from their home chats or a recurring habit. A topic (`~ragebait bob twin primes`) narrows the source material. The model outlines the event before writing the joke; output checks reject invented quotes and jokes that need missing context. |
| `~ragebait ref [n]` | anyone | Show the source for the last ragebait in this chat; `n=2` shows the one before. No model call. |

These commands compare patterns in archived messages. The scores depend on
the messages and channels included.

### Moderation and utilities

| Command | Access | What it does |
| --- | --- | --- |
| `~help [page\|archive\|personas\|analysis\|translation\|utility\|ai\|command]` | anyone | List command groups, show a group or command, or check which commands use a local model. `~mimic` and `~markov` work but are unlisted; admin commands are listed through `~admin`. |
| `~admin` | anyone | List admin and super-admin commands. They are omitted from `~help` and require the permissions shown here. |
| `~experimental` | anyone | List experimental commands such as `~askchat`, `~emote`, `~why emote` and `~irony`, including their `raw` options. |
| `~ping` | anyone | Show response latency and host statistics. |
| `~leastused [n] [months]` | anyone | Rank the channel's 7TV emotes by use. Each emote counts once per message, duplicate log entries are combined, and counts account for emote age. `~leastused most [n]` shows the most used. Does not edit the emote set. |
| `~emotes add\|remove\|alias\|prune ...` | editors / super admin | Edit the channel's 7TV emote set. `add <name\|7tv-link> [as <alias>]` adds the most-used matching emote; `remove <name>`; `alias <name> <newname>` renames one; `replace <name> <new-name\|link>` swaps one keeping the name. Trusted `[seventv] editors` do these one at a time (rate-limited); `prune <n> [months]` (super admin) previews the n least-used and needs `yes`. Needs a 7TV editor token in config. |
| `~artifacts` | anyone | Show which generated analysis files are missing or out of date. |
| `~banuser <name>` | super admin | Ban a chatter from using bot commands. Translation/archive capture are unaffected. |
| `~banuser list` | super admin | Show command-banned users. |
| `~unbanuser <name>` | super admin | Remove a command ban. |
| `~warnings [n]` | super admin | Review recent anti-spam cooldown offenses (the escalating cooldowns described below). |
| `~model [status\|off\|on\|clear]` | super admin | Show or clear the local-model queue, or turn model calls on or off. Turning them off clears pending work; a running command finishes. `[llm] enabled = false` sets the startup default. `~modelqueue` is an unlisted alias. |
| `~announce [now [chat]]` | super admin | Show the schedule for configured reminder posts, or post now. `[announce]` sets channels, message and timing: at most `max_per_day` posts in a rolling 24 hours, at least `min_gap_hours` apart, with a randomized extra wait. Posts only in active chats; an empty `channels` list disables scheduled posts. |
| `~gojomons` | super admin | Post the project-site link (config `[announce] site_url`) in the chat it's called in. |
| `~axismerge <canonical> <dup> [flip]` | super admin | Merge duplicate trait scales (`flip` reverses the second scale). `~axismerge del <axis>` deletes a scale; `~axismerge list` shows saved scales. The admin chooses which scales to merge. |

## Command limits

Sending a third extra command while your previous command is still running
gets a warning, and that command is skipped. Another attempt within 15
minutes starts a per-user cooldown: 3 minutes initially, doubling for repeat
offenses up to 15 minutes. During a cooldown the bot sends one notice, then
ignores further commands. Strikes expire after two quiet hours.
`~warnings` shows recorded cooldowns.

## Channel personas

One chatter persona can be active per channel. It can respond to topics found
in that chatter's history, send occasional messages when chat is quiet, and
reply in a Twitch thread when the triggering message has an ID. Full
`~generate` recipes cannot yet be used as channel personas.

## Required data files

Some analysis commands need files built from the archive. `~artifacts` shows
what is missing or out of date. The [architecture guide](ARCHITECTURE.md#analysis-data-files)
lists the files, build tools and commands that use them.
