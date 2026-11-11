# Setup

Install once to run the Twitch bot or use the offline chat tools. The bot needs
Twitch credentials; offline search and Markov generation need only chat logs.
A local model server is optional for generated replies.

## 1. Install

Python 3.12 or newer (developed on 3.13). TwitchIO is pinned to 2.10.0 because
`chatbot.py` refreshes the token through 2.10 internals.

```sh
python -m venv .venv
.venv\Scripts\activate                  # Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env                  # Linux/macOS: cp
copy config.example.toml config.toml
```

`config.toml` holds channel names, admins, paths and feature toggles. `.env`
holds secrets. Both are gitignored. `pyproject.toml` lists the same
dependencies for `poetry install` if you prefer Poetry.

## 2. Run the Twitch bot

1. Create a Twitch application at `https://dev.twitch.tv/console/apps`. Add
   `http://localhost:3000` under OAuth Redirect URLs. Put the client id and
   secret in `.env` as `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET`.
2. Translation provider: a DeepL API key (`DEEPL_API_KEY`, free tier at
   `https://www.deepl.com/pro-api`) or a Google Cloud Translation
   service-account file (`GOOGLE_APPLICATION_CREDENTIALS`). DeepL is tried
   first. Without either provider, translation is disabled.
3. In `config.toml`, set `[bot] channels` to the channels the bot joins and
   `[auth] admins` and `super_admins` to Twitch logins.
4. Create the settings database and fetch the bot account's first token. The
   token helper opens Twitch in your browser, catches the redirect on
   localhost, and writes `data/unsynced/token_data.json`; the bot refreshes it
   from then on. Log in to Twitch as the bot account before you approve.

   ```sh
   python tools/setup/init_db.py
   python tools/setup/get_initial_token.py
   ```

5. Run it:

   ```sh
   python chatbot.py
   ```

   The log shows the login, the joined channels and, if `[bot] ready_message`
   is set, the greeting it posts. `~ping` answers with latency and host stats;
   `~help` lists the public commands.

6. Turn translation on. It starts off for every channel:

   | Command | Who | Effect |
   | --- | --- | --- |
   | `~global_autotl on` | super admin | master switch |
   | `~chan_autotl <channel> on` | super admin | per-channel switch |
   | `~autotl`, `~setlang ES`, `~tloutput local\|whisper\|channel <name>` | admin | your own translations and where they go |
   | `~practice on es,ja en` | anyone | whispers study-language translations of your native-language messages; posts native-language translations of your study-language messages in chat |
   | `~romanize on`, `~speak <lang>` | anyone | readings for non-Latin scripts; declare a language so short messages still translate |
   | `~notranslate <user>` | super admin | skip a chatter the detector misreads |

   Twitch limits whispers from bots; the bot account needs a verified phone
   number and the `user:manage:whispers` scope (requested by the token helper),
   and whispers can still be dropped.

## 3. Import, search and generate messages

1. Import Chatterino logs. Chatterino stores one folder per channel under
   `%AppData%\Chatterino2\Logs\Twitch\Channels`; pass that folder, or set
   `[archive] chatterino_logs` once and omit the argument. The synthetic log in
   `examples/sample-logs` works as a first run.

   ```sh
   python tools/archive/ingest_chatterino.py examples/sample-logs
   ```

   Unchanged files are skipped; files that grew are re-imported.
   With the bot running and `[archive] live_capture = true`, every
   message it sees is added as well.

2. Search from a terminal (`said`, `near`, `quote`, `stats`, `search`), or in
   chat with `~said`, `~regex`, `~quote`, `~firstseen`, `~chatstats`,
   `~regulars`:

   ```sh
   python tools/archive/ask_archive.py said chatter_01 sourdough starter
   python tools/archive/ask_archive.py stats chatter_01
   ```

3. Generate a Markov message, without a model server. A chatter needs at least 40 archived
   messages. Preview in a terminal, or post in chat with `~markov <user>`
   (`[persona] mimic_enabled`):

   ```sh
   python tools/archive/persona_preview.py chatter_01 5 --seed 7
   ```

4. Preview the messages selected for a model reply. `persona_rag_preview.py`
   prints examples of the chatter's writing, topic matches and conversation
   snippets without calling a model:

   ```sh
   python tools/archive/persona_rag_preview.py chatter_01 sourdough --seed 7
   ```

5. Optional local model for `~persona`, `~hyper`, `~generate` and the resident
   persona modes. Install LM Studio (or any server that speaks
   `/v1/chat/completions`), load a chat model and start its server. The default
   `[llm] endpoint` is `http://127.0.0.1:1234/v1/chat/completions`; `model =
   "local"` picks the first loaded chat model. `[llm] enabled = false` starts with
   model calls disabled, and `~model off` / `~model on` switch it at
   runtime. Archive search and Markov personas keep working either way.

6. Optional analysis artifacts (`~whosaid`, `~markers`, `~like`, `~vibes`,
   `~traits`, `~top`, ...). The classifier and style profiles need only the
   archive; embeddings need an embedding model at the same endpoint
   (`[llm] embed_model`). `~artifacts` and `python tools/check/artifact_status.py`
   report what is missing.

   ```sh
   python tools/build/rebuild_persona_artifacts.py --skip-embeddings   # classifier, style profiles, fact bank
   python tools/build/rebuild_persona_artifacts.py                     # everything, with an embedding model served
   ```

7. Fine-tuning a voice model is a separate offline path; see
   [FINE_TUNING.md](FINE_TUNING.md).

The [walkthrough](../examples/README.md) shows search results, selected persona
context and Markov messages from the synthetic logs.

## 4. Config toggles

| Setting | Default | Controls |
| --- | --- | --- |
| `[bot] channels`, `ready_message` | `["your_channel"]`, `""` | channels joined; greeting on connect |
| `[auth] admins`, `super_admins` | your channel | who may change translation settings and run gated commands |
| `[translation] min_foreign_share`, `min_words`, `min_short_confidence` | 0.63, 4, 0.55 | how sure the detector must be before a line is translated |
| `[archive] live_capture` | true | write live chat into the archive |
| `[archive] chatterino_logs` | `""` | default folder for the ingest tool |
| `[archive.user_aliases]`, `[archive.channel_aliases]` | empty | merge alt accounts and renamed channels at query time |
| `[persona] mimic_enabled` | true | `~markov` / `~mimic` |
| `[persona] reaction_chance`, `reaction_directed_chance` | 0.0 | unprompted persona lines; 0 keeps the bot silent unless asked |
| `[persona] blocklist_file` | `data/unsynced/blocklist.txt` | denylist checked before anything generated is posted; no file means no filter |
| `[llm] enabled`, `endpoint`, `model`, `embed_model` | true, LM Studio, `local`, `""` | model personas and embedding-based analysis |
| `[llm] semantic_retrieval` | false | meaning-based retrieval for persona evidence (needs the message index) |
| `[analysis] channels`, `max_authors`, `min_messages` | bot channels, 40, 300 | the chatters included in analysis |
| `[announce]`, `[seventv]` | off | periodic posts; 7TV emote-set editing |

## 5. Windows launchers

`scripts/windows/` holds double-click launchers. Each one changes to the
project root itself, so they can be run from anywhere.

| Launcher | Does |
| --- | --- |
| `1-setup.bat` | create `.venv`, install requirements, create the settings database |
| `2-login.bat` | run the token helper |
| `3-run.bat` | run the bot in a visible window |
| `4-run-tests.bat` | run the unit tests |
| `run-background.vbs` | run the bot hidden through `_bot-loop.bat`, which restarts it after a crash and logs to `data/bot.log` |
| `show-log.bat` | follow `data/bot.log` |
| `stop-bot.bat` | stop the background bot until the next login |
| `stop-bot-FOREVER.bat` | stop it and remove the login autostart shortcut |
| `9-backup-unsynced-data.bat` | zip `data/unsynced` artifacts into `_private/backups` |
| `10-rebuild-persona-artifacts.bat` | rebuild the analysis artifacts in the foreground |
| `10-rebuild-persona-artifacts-background.bat` | same, in the background with logs under `data/unsynced` |
| `14-freshness-check.bat` | run `tools/check/freshness_check.py` |

To start the bot at login, put a shortcut to `scripts\windows\run-background.vbs`
in your Startup folder (`shell:startup`).

## 6. Checks

```sh
python -m unittest discover -s tests -q
python tools/check/audit_commands.py
python tools/check/check_readme_commands.py
python tools/check/freshness_check.py
```

The tests use temporary databases and never connect to Twitch. The command
audit imports every command module and checks it has an async handler, a
description and a row in [COMMANDS.md](COMMANDS.md).

[Project overview](../README.md) | [Command reference](COMMANDS.md) | [Architecture](ARCHITECTURE.md)
