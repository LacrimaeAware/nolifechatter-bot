# Architecture

NoLifeChatter is one Python process built on TwitchIO 2.10. It has two
capabilities that share a small core and one SQLite archive. Either capability
can be used without the other: a translation-only bot never needs a model
server, and the archive tools run without a Twitch connection.

| Capability | What it does | Where it lives |
| --- | --- | --- |
| A. Translation bot | Detects the language of each chat line locally, translates it through DeepL or Google Cloud Translation, runs language practice through whispers and chat, romanizes Japanese, Korean and Thai | `services/message_service.py` (translation and practice mode), `services/translators.py`, `utils/language_detect.py`, `utils/speaker_profile.py`, `utils/romanize.py`, `utils/roman_scripts/`, `utils/translate_optout.py`, commands `autotl`, `chan_autotl`, `global_autotl`, `notranslate`, `practice`, `romanize`, `setlang`, `speak`, `tloutput` |
| B. Chat archive and personas | Stores every message the bot sees plus imported Chatterino logs in SQLite with FTS5, answers archive questions in chat, builds personas from a chatter's own history (Markov without a model, retrieved examples with a local model) | the archive, persona and analysis sections below |

## Shared core (repository root)

- `chatbot.py`: entry point. Creates the TwitchIO bot, keeps the OAuth token
  fresh in a background thread (`utils/token_manager.py`), restarts on a silent
  connection, and starts the periodic announcer.
- `config.py`: loads `config.toml` (channels, admins, paths, toggles) and `.env`
  (secrets).
- `handlers.py`: one entry per message. Records the message in the archive when
  `[archive] live_capture` is on, then routes it to the command processor (prefix
  `~`) or to the message service (translation, persona reactions).
- `command_processor.py` and `command_registry.py`: discover `commands/*.py`
  (a module with `handle_<name>` is the command `~name`), check command bans
  (`utils/command_bans.py`), apply the anti-spam cooldown
  (`utils/cooldowns.py`), and send model-heavy commands through the shared
  model queue (`services/model_queue.py`).
- `auth.py`: admin and super admin checks from `[auth]`.
- `utils/user_settings.py`: per-user settings in `data/synced/bot_settings.db`.
- `services/emotes.py`: per-channel 7TV, BTTV and FFZ emote names, used to strip
  emotes before language detection.
- Utility commands: `help`, `admin`, `experimental`, `ping`, `artifacts`,
  `banuser`, `unbanuser`, `warnings`, `model` (`modelqueue` is an alias).

Message path: Twitch IRC, `Bot.event_message`, `MessageHandler.process_message`,
archive capture, then `CommandProcessor.process_command` or
`MessageService.handle_regular_message`.

## B1. Archive layer

- `utils/chat_archive.py`: schema, the Chatterino log parser, FTS5 search, close
  match search, context windows and alias handling. Design notes and the log
  format are in [CHAT_ARCHIVE.md](CHAT_ARCHIVE.md).
- `tools/archive/ingest_chatterino.py` imports a Chatterino `Channels` folder;
  `tools/archive/ask_archive.py` and `tools/archive/ask_chat.py` query the
  archive from a terminal (`utils/archive_qa.py`, `utils/fact_bank.py`).
  Archive question answering combines keyword and embedding retrieval, adds
  surrounding conversation from the same source, and supplies those messages
  to the model. Raw mode returns the selected messages without a model call.
- `utils/message_quality.py` holds the junk filters (commands, pasted logs,
  emote spam) shared by every archive consumer. `utils/emote_usage.py` counts
  emote use for `~leastused`.
- Commands: `said`, `saidnext`, `saidmost`, `regex`, `userregex`, `quote`,
  `random`, `firstseen`, `chatstats`, `regulars`, `askchat`, `leastused`.

## B2. Persona generation

- Markov personas, no model: `utils/persona_markov.py`; commands `markov` and
  `mimic`; `tools/archive/persona_preview.py` prints samples in a terminal.
- Retrieved-example personas with a local model: `utils/persona_llm.py` selects
  messages from the author's history and the live conversation, builds the
  prompt and checks candidates; `utils/persona_generate.py` handles `~generate`
  recipes; `utils/resident_persona.py` and the resident engine inside
  `services/message_service.py` run channel-scoped personas; `utils/ragebait.py`,
  `utils/obsessions.py` and `utils/reaction_tracker.py` support the persona
  commands. `services/llm.py` is the OpenAI-compatible client and
  `services/model_queue.py` queues requests to it (availability
  probing, queue position messages, the `~model` on/off gate).
  `tools/archive/persona_rag_preview.py` shows the selected messages without
  calling a model. Commands: `persona`, `pers`, `hyper`, `generate`, `ragebait`,
  `botpersona`, `botmode`, `botcontext`, `botchance`.
- Output gate: `utils/output_filter.py` checks every generated line against a
  local denylist file before it is posted.

## B3. Analysis readouts

Offline artifacts built by `tools/build/*` (authorship classifier, style
profiles, person embeddings, per-message index, fact bank, user profiles, emote
registry and semantics) and read at runtime by `whosaid`, `markers`, `like`,
`twin`, `vibes`, `traits`, `style`, `top`, `bottom`, `distinct`, `axis`,
`axismerge`, `why`, `emote`, `explain`, `funny` and `irony` through
`utils/persona_classifier.py`, `utils/behavior_profile.py`,
`utils/persona_embeddings.py`, `utils/persona_msg_index.py`,
`utils/persona_traits.py`, `utils/persona_axes.py`,
`utils/comedic_influence.py`, `utils/irony.py`, `utils/emote_explain.py`,
`utils/emote_meaning.py` and `utils/user_profiles.py`.
`tools/build/rebuild_persona_artifacts.py` runs the build tools in order;
`tools/check/artifact_status.py` and `~artifacts` report missing or stale
artifacts. The embedding-based artifacts need an embedding model served at
`[llm] endpoint` (`[llm] embed_model`); a command whose artifact is missing says
so instead of failing.

## Channel tools

`commands/emotes.py` with `utils/seventv.py` edits the channel's 7TV emote set
(editors listed in `[seventv]`); `commands/announce.py` with `utils/announcer.py`
posts a configured message on a bounded cadence; `commands/gojomons.py` posts a
configured site link.

## Offline experiments

`experiments/finetune/` is the LoRA path (export training data from the
archive, train on a rented GPU, merge to GGUF); see
[FINE_TUNING.md](FINE_TUNING.md). `experiments/eval/` holds the evaluation
harnesses listed in [RESEARCH_QUESTIONS.md](RESEARCH_QUESTIONS.md).

## Operations

`tools/setup/` (database, first token, settings lookup), `tools/check/`
(command audit, command doc sync, freshness check, artifact status),
`tools/maint/` (log rotation, backups, background rebuilds) and the Windows
launchers in `scripts/windows/`. Runtime data lives under `data/` and is
gitignored: `data/synced/bot_settings.db` (settings, bans, cooldown offenses)
and `data/unsynced/` (archive, tokens, artifacts, logs).

## Model requests

Commands that use a local model share one queue across channels. Commands
such as `~persona`, `~hyper`, LLM `~generate`, dynamic `~top`/`~bottom`,
`~axis`, uncached/`words`-mode `~why`, and `~irony` answer one at a time. The
first use of built-in `~traits`/`~distinct` also waits while its trait scales
load. Later uses and cached-scale variants use the loaded files; raw results
do not need a model call. `~askchat` and emote explainers search the archive
first. They request a model-written answer only when the queue is idle;
otherwise they return the search result.

The queue reports when work starts and its position while waiting. It allows
one active request per user, rejects duplicate requests, and reports whether
the model is busy or its server is unavailable. Super admins can inspect or
clear it with `~model`.

## Channel persona state

Active personas are saved in `data/unsynced/resident_personas.json`; configured
output prefixes are also runtime state under `data/unsynced`. Triggered replies
use Twitch reply tags when the incoming message has an ID and TwitchIO exposes
the low-level reply method. Otherwise the bot sends a normal channel message.

Reply selection uses configured probabilities, direct-message and greeting
rules, a curved FTS topic-match boost, cooldowns and limits on idle-message
attempts. The persona prompt can return STOP instead of a reply.

Trait/topic-only generation recipes use example sentences for the chosen
trait poles and instructions to vary the result. Chatter recipes add selected
messages from each user and ask for a blend when several users are named.

## Analysis data files

Some commands read the SQLite archive directly; others need generated files:

The message index and person vectors serve different purposes. The message
index retrieves passages from one author's history. Person vectors pool that
author's utterances for similarity and trait-scale comparisons. Short bursts
are merged within the same channel before embedding; alias and model metadata
helps detect indexes that need rebuilding.

Set `[llm] embed_model` to the ID of a served embedding model. The server at
`[llm] endpoint` must also support `/v1/embeddings`. After importing the archive
and selecting the `[analysis]` roster, build both artifacts:

```sh
python tools/build/build_message_index.py --force
python tools/build/build_persona_embeddings.py --from-message-index
```

For semantic additions to persona prompts, set `[llm] semantic_retrieval = true`.
Author-scoped `~askchat` uses its dense retrieval path independently of that
switch. Each new semantic query needs an embedding call; if it fails, archive
questions fall back to keyword search. Existing compatible person vectors let
`~vibes` and `~twin` compare chatters without calling the embedding server.
Trait commands can reuse cached scales, but new scales or missing pole/emote
vectors need the server.

| File | Built by | Used by |
| --- | --- | --- |
| `data/unsynced/chat_archive.db` | live capture and `tools/archive/ingest_chatterino.py` | archive, stats, Markov, persona message examples |
| `data/unsynced/persona_classifier.pkl` | `tools/build/train_classifier.py` | `~whosaid`, `~markers`, `~like`, persona evaluation tools |
| `data/unsynced/persona_embeddings.pkl` | `tools/build/build_persona_embeddings.py` | `~vibes`, `~twin`, trait averages |
| `data/unsynced/msg_index/` | `tools/build/build_message_index.py` | author-scoped `~askchat`, `~why`, burst `~top`, semantic persona retrieval |
| `data/unsynced/fact_bank.jsonl` | `tools/build/build_fact_bank.py` | `~askchat`, offline archive questions |
| `data/unsynced/user_profiles.json` | `tools/build/build_user_profiles.py` | confirmed persona facts, `~askchat`, irony history checks |
| `data/unsynced/emote_semantics.pkl` + `data/unsynced/emote_tag_vecs.pkl` | `tools/build/build_emote_semantics.py` + emote tag-vector tooling | `~emote`, `~explain emote`, `~why emote` |

Use `~artifacts` or `python tools/check/artifact_status.py` to check whether these
artifacts are missing, missing build metadata, or built with the current
semantic unit/model.

After identity merges, embedding-model changes, or major filter changes, run
`scripts/windows/10-rebuild-persona-artifacts.bat` or `tools/build/rebuild_persona_artifacts.py`.
For an unattended run, use `scripts/windows/10-rebuild-persona-artifacts-background.bat`; it
writes stdout/stderr logs under `data/unsynced`.
Embeddings and indexes use merged utterances by default;
`--semantic-unit message` indexes messages separately.
