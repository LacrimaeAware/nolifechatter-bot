# Architecture

NoLifeChatter is one Python process built on TwitchIO 2.10. It has two
capabilities that share a small core and one SQLite archive. Either capability
can be used without the other: a translation-only bot never needs a model
server, and the archive tools run without a Twitch connection.

| Capability | What it does | Where it lives |
| --- | --- | --- |
| A. Translation bot | Detects the language of each chat line locally, translates it through DeepL or Google Cloud Translation, runs a practice mode over whispers, romanizes Japanese, Korean and Thai | `services/message_service.py` (translation and practice mode), `services/translators.py`, `utils/language_detect.py`, `utils/speaker_profile.py`, `utils/romanize.py`, `utils/roman_scripts/`, `utils/translate_optout.py`, commands `autotl`, `chan_autotl`, `global_autotl`, `notranslate`, `practice`, `romanize`, `setlang`, `speak`, `tloutput` |
| B. Chat archive and personas | Stores every message the bot sees plus imported Chatterino logs in SQLite with FTS5, answers archive questions in chat, builds personas from a chatter's own history (Markov without a model, retrieved examples with a local model) | the archive, persona and analysis sections below |

## Shared core (repository root)

- `chatbot.py`: entry point. Creates the TwitchIO bot, keeps the OAuth token
  fresh in a background thread (`utils/token_manager.py`), restarts on a silent
  connection, and starts the periodic announcer.
- `config.py`: loads `config.toml` (channels, admins, paths, toggles) and `.env`
  (secrets). Nothing channel-specific is in code.
- `handlers.py`: one entry per message. Records the message in the archive when
  `[archive] live_capture` is on, then routes it to the command processor (prefix
  `~`) or to the message service (translation, persona reactions).
- `command_processor.py` and `command_registry.py`: discover `commands/*.py`
  (a module with `handle_<name>` is the command `~name`), check command bans
  (`utils/command_bans.py`), apply the anti-spam cooldown
  (`utils/cooldowns.py`), and send model-heavy commands through the shared
  model lane (`services/model_queue.py`).
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
- `utils/message_quality.py` holds the junk filters (commands, pasted logs,
  emote spam) shared by every archive consumer. `utils/emote_usage.py` counts
  emote use for `~leastused`.
- Commands: `said`, `saidnext`, `saidmost`, `regex`, `userregex`, `quote`,
  `random`, `firstseen`, `chatstats`, `regulars`, `askchat`, `leastused`.

## B2. Persona generation

- Markov personas, no model: `utils/persona_markov.py`; commands `markov` and
  `mimic`; `tools/archive/persona_preview.py` prints samples in a terminal.
- Retrieved-example personas with a local model: `utils/persona_llm.py` selects
  evidence from the author's history and the live conversation, builds the
  prompt and checks candidates; `utils/persona_generate.py` handles `~generate`
  recipes; `utils/resident_persona.py` and the resident engine inside
  `services/message_service.py` run channel-scoped personas; `utils/ragebait.py`,
  `utils/obsessions.py` and `utils/reaction_tracker.py` support the persona
  commands. `services/llm.py` is the OpenAI-compatible client and
  `services/model_queue.py` is the single lane in front of it (availability
  probing, queue position messages, the `~model` on/off gate).
  `tools/archive/persona_rag_preview.py` shows the selected evidence without
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
`tools/build/rebuild_persona_artifacts.py` runs the pipeline in order;
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

## Known seams

- `services/message_service.py` contains both the translation flow and the
  resident persona engine. Splitting it into two services is the next
  structural step; the import graph is otherwise already separated by folder.
- Analysis commands and the build scripts under `tools/build/` ship together;
  they are optional and need built artifacts before they answer.
