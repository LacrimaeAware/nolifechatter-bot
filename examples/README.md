# Example: import, search and generate messages

`sample-logs/examplechat/` contains two Chatterino-format logs with invented
messages and usernames (`chatter_01` to `chatter_06` and `examplebot`). They
include chat, header, system and moderation lines.

Run the commands below from the repository root with the project's virtual
environment active. They need `config.toml` (copy `config.example.toml`; the
defaults are fine) and nothing else: no Twitch connection, no model server.
The archive is created at `data/unsynced/chat_archive.db`.

## Ingest the logs

```sh
python tools/archive/ingest_chatterino.py examples/sample-logs
```

Output (the timestamp at the start of each log line is omitted here):

```text
INFO - examplechat: +122 messages (-> channel 'examplechat')
INFO - Done. files=2 (skipped 0 unchanged) | messages=122 system=5 headers=4 empty=0 modactions=2
INFO - Archive now: 122 messages, 7 authors, 1 channels (data/unsynced/chat_archive.db)
```

The two `# Start logging` / `# Stop logging` pairs are headers, `connected` and
`joined channel` lines are system lines, and the two `chatter_05 timed out ...`
lines are moderation actions that look like chat and are filtered out. Running
the same command again skips both files:

```text
INFO - Done. files=2 (skipped 2 unchanged) | messages=0 system=0 headers=0 empty=0 modactions=0
INFO - Archive now: 122 messages, 7 authors, 1 channels (data/unsynced/chat_archive.db)
```

## Search the archive

```sh
python tools/archive/ask_archive.py stats chatter_01
```

```text
chatter_01: 60 messages, first 2026-01-05 18:00:31, last 2026-01-06 18:01:20, avg 49 chars, busiest hour 18:00
```

Exact phrase search (FTS5, whole words, any case):

```sh
python tools/archive/ask_archive.py said chatter_01 sourdough starter
```

```text
chatter_01 said "sourdough starter": 2 time(s)
  [2026-01-05 18:01:07] #examplechat: sourdough starter day three and it finally has bubbles
  [2026-01-06 17:32:20] #examplechat: the sourdough starter is the whole secret, feed it every morning
```

The same search across every author:

```sh
python tools/archive/ask_archive.py search boat skip
```

```text
[2026-01-05 18:05:20] #examplechat chatter_01: it is all about the menu buffer before the boat skip
[2026-01-05 18:12:31] #examplechat chatter_01: run starting, wish me a good boat skip
[2026-01-05 18:13:02] #examplechat chatter_02: boat skip or riot
[2026-01-05 18:19:10] #examplechat chatter_01: boat skip clean breadChamp breadChamp
[2026-01-05 18:24:02] #examplechat chatter_01: gracias gracias, the boat skip carried that run
[2026-01-05 18:31:20] #examplechat chatter_01: boat skip dropped again, the timing window is two frames
[2026-01-06 17:37:00] #examplechat chatter_01: menu buffer landed, boat skip landed, this is the one
[2026-01-06 17:38:50] #examplechat chatter_01: sub 41 after three years of grinding the boat skip
[2026-01-06 17:51:30] #examplechat chatter_01: boat skip dropped, the two frame window got me again
[2026-01-06 17:52:30] #examplechat chatter_01: reset, that is the rule, dropped boat skip is a reset
[2026-01-06 17:54:40] #examplechat chatter_01: castle 12:35, buffer landed, boat skip landed
```

Close matches when you only half remember the line (punctuation, case and
spacing are normalized, then the closest lines are ranked):

```sh
python tools/archive/ask_archive.py near chatter_01 starter finally alive
```

```text
Closest lines by chatter_01 to "starter finally alive":
  84.4% [2026-01-05 18:01:44] #examplechat: my starter is finally alive!!
```

In chat, `~said chatter_01 sourdough starter`, `~chatstats chatter_01` and
`~regex chatter_01 boat skip` answer the same questions in Twitch-sized
replies.

## Preview the messages selected for a model reply

`~persona chatter_01 <message>` supplies a local model with examples from the
chatter's history: a random sample, topic matches and short conversation
snippets. This tool prints the selected evidence without calling a model:

```sh
python tools/archive/persona_rag_preview.py chatter_01 sourdough --seed 7 --show-relevant 5 --show-signature 5 --show-snippets 3
```

```text
User: chatter_01
Canonical author: chatter_01
Author keys searched: chatter_01 (60)
Exemplar budget: 150
Selected: 58 random signature + 0 flat relevant + 2 snippets
Retrieval terms: sourdough
Semantic retrieval: off
Directed query: sourdough

Chat-moment snippets (2 of 2):
   1. chatter_02: gg ez
chatter_03: what are we baking today
>> chatter_01: sourdough starter day three and it finally has bubbles
chatter_02: bubbles pog
chatter_01: my starter is finally alive!!
   2. chatter_01: open crumb, blistered crust, the overnight cold proof did its job
chatter_06: that is a bakery loaf
>> chatter_01: the sourdough starter is the whole secret, feed it every morning
chatter_04: que rico
chatter_01: next loaf gets some rye in the mix for flavor

Relevant examples (0 of 0):
  (none)

Random signature examples (5 of 58):
   1. crumb reveal time breadChamp
   2. boat skip dropped again, the timing window is two frames
   3. eleven resets and one loaf, balanced day
   4. dutch oven at 250 for twenty minutes with the lid on then twenty without
   5. about a week if your kitchen is warm, two if it is cold
```

The two sourdough matches appear as snippets, with `>>` marking the matched
line. The budget of 150 exemplars comes from `[llm] exemplars`. This example
uses keyword retrieval; the optional message-vector index adds semantic matches.

## Optional Markov baseline

For comparison, the no-model generator uses a word-level Markov chain over everything the chatter wrote. It needs at least
40 archived messages. `--seed` makes the sample reproducible; without it every
run differs.

```sh
python tools/archive/persona_preview.py chatter_01 5 --seed 7
```

```text
  ok bread check, the dough has doubled already, warm kitchen
  about a week if your kitchen is warm, two if it is all about the menu buffer before the boat skip
  about a week if your kitchen is warm, two if it is happy and like nail polish when it is happy and like nail polish when it is all about the menu buffer before the load so the input carries
  after this loaf i am doing the any% run again
  41:05 new pb!!! PogBread
```

With the bot running, `~markov chatter_01` posts one such line after the
output filter has checked it.

## Use a model with the bot

- For model personas, run LM Studio with a chat model and use
  `~persona <user> [message]`; [Setup](../docs/SETUP.md) covers the switches.
- [Generation and channel modes](../docs/GENERATE_AND_BOT_MODES.md) covers
  multi-chatter recipes and resident personas. [Analysis data files](../docs/ARCHITECTURE.md#analysis-data-files)
  describes the separate message and person indexes.
- [Fine-tuning](../docs/FINE_TUNING.md): optional LoRA training and local-model setup.
