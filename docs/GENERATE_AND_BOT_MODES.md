# Message generation and channel personas

`~persona <user> [message]` requests a reply in one chatter's style.
`~generate` creates one message from a combination of users, traits and topics.
`~botpersona` keeps a chosen persona active in a channel and controls when it replies.

## Model persona replies

The persona engine prepares a prompt from the chatter's saved messages,
topic matches, short conversation snippets and recent channel chat. A stable
sample supplies recurring writing habits; retrieved examples supply context.
Semantic matches can supplement keyword search when the message index is
configured. Recorded profile claims from the profile builder are included
when available.

For `~persona`, the engine can sample several replies. Candidate checks look
for copied source lines, echoes of other chatters, speaker labels, URLs,
commands and assistant-style preambles. Remaining candidates are ranked for
the requested voice, topic fit, length and distance from source examples.
Directed questions can also use a separate model check of whether each
candidate answers the question.

Channel personas use the same generator with one candidate and the reply
rules below. `~generate` uses a separate recipe prompt with the selected
chatters' examples and trait hints. Both paths can use an untuned local model.
The optional [fine-tuning workflow](FINE_TUNING.md) changes model weights;
retrieval supplies saved messages in the persona prompt.

## Generate a message

Combine tags to describe the message:

    ~generate <tags...>

Tag kinds (order never matters; comma or space separated):
- **chatter names** - one uses that person's style; several blend their styles
- **trait poles** - optimist/doomer, professor/brainrot, menace/wholesome,
  ironic/sincere, unhinged/chill: choose an exaggerated style
- **chat=<channel>** - only use the chatters' messages from that channel
  (repeatable; each adds a channel to the allowed set)
- **year=<YYYY>** - only their messages from that year
- **topic=... / any leftover words** - free-text topic the message is about
- **engine=llm|markov** - markov works for chatter tags only (no traits/topic)
- **model=llama|lora** - LLM override, same shortcuts as ~persona
- **a saved combo name** - expands to its stored tags (see below)

Examples:
    ~generate somechatter doomer
    ~generate chatterA chatterB chat=somechannel year=2022
    ~generate optimist topic=world of warcraft
    ~generate optimist            <- generic maximal optimist, varied each call

Recipes with only traits and topics use the model without a chatter's saved
messages. Chatter recipes supply examples from each selected user, within the
channel and year filters. Generated messages are checked for URLs, command
lines and terms in the configured output denylist.

## Saved recipes

    ~generate save florpface chatterA chatterB optimist chat=somechannel
    ~generate florpface                  <- uses the recipe
    ~generate florpface professor        <- recipe + extra tags stacked on top
    ~generate list / ~generate del florpface

Recipes belong to the Twitch user who saves them and are stored in the
settings database's `gen_combos` table. A recipe cannot reference another recipe.

## Channel personas

Super admins can keep one chatter persona active per channel. Full
`~generate` recipes and saved recipes cannot yet be used this way.

- **regular** - may respond to normal incoming chat, with higher odds for
  direct messages, greetings, and topics the persona has many archived hits
  for. It can also send rare idle/empty-chat lines after chat has been quiet,
  with a limit on consecutive bot messages.
- **response** - only replies when @mentioned, in the resident persona.
- **random** - random chance per message (chance settable by command).
- **silent** - commands only.

Live commands:

    ~botpersona status [chat=<channel>]
    ~botpersona off [chat=<channel>]
    ~botpersona <user> [chat=<channel>] [minutes=360] [mode=regular|response|random|silent] [chance=] [topic=] [curve=] [directed=] [directed_cooldown=] [idle=]
    ~botmode regular|response|random|silent [minutes] [chat=<channel>]
    ~botcontext [chat=<channel>] <free text|clear>
    ~botchance <base> [directed] [chat=<channel>] [topic=] [idle=] [greeting=] [cooldown=]

Time-limited modes expire automatically. Replies can also carry a configured
prefix. The [architecture guide](ARCHITECTURE.md#channel-persona-state) describes
where settings are stored and how Twitch reply threads are used.

## Command limits

- Super admins can use `~banuser <name>` and `~unbanuser <name>` to control who
  may use bot commands.
- Repeated command stacking triggers [cooldowns](COMMANDS.md#command-limits).
  `~warnings` shows recent cooldowns.
- Model commands and channel-persona replies share a queue. It reports queue
  positions, allows one active request per user and rejects duplicate requests.
  Super admins can inspect or clear it with `~model`.

## Local files and maintenance

Channel-persona settings are saved in `data/unsynced/resident_personas.json`.
The queue coordinates requests within one bot process. Pause the bot while
running offline maintenance that also uses the model server.
