# NoLifeChatter

A Twitch bot with two separate capabilities that share one process and one
SQLite archive:

- **A. Translation bot.** Detects the language of chat lines locally (lingua),
  translates through DeepL or Google Cloud Translation, runs a practice mode
  over whispers, and romanizes Japanese, Korean and Thai.
- **B. Chat archive and personas.** Stores every message it sees, plus your
  Chatterino logs, in SQLite with FTS5; answers `~said`, `~quote`, `~regex`,
  `~chatstats` in chat; builds personas from a chatter's own history, either a
  Markov version that needs no model or a retrieved-example version that
  prompts a local OpenAI-compatible model (LM Studio by default).

Python 3.12 or newer, TwitchIO 2.10. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
says which directory each part lives in.

## A. Run the translation bot on your channel

You need a Twitch account for the bot, a Twitch application (client id and
secret with `http://localhost:3000` as an OAuth redirect URL) and a DeepL API
key (free tier) or a Google service-account file.

```sh
python -m venv .venv
.venv\Scripts\activate                 # Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env                 # Linux/macOS: cp; add client id, secret, DeepL key
copy config.example.toml config.toml   # channels, admins, toggles
python tools/setup/init_db.py
python tools/setup/get_initial_token.py   # opens Twitch in your browser once
python chatbot.py
```

What to expect: the bot logs in, joins `[bot] channels` and answers `~ping` and
`~help`. Auto-translation starts switched off. A super admin turns it on with
`~global_autotl on` and `~chan_autotl <channel> on`; chatters use `~autotl`,
`~setlang ES`, `~practice on es,ja en`. Every step is in
[docs/SETUP.md](docs/SETUP.md).

## B. Archive your chat and build a persona from your own logs

```sh
python tools/archive/ingest_chatterino.py examples/sample-logs   # or your Chatterino Channels folder
python tools/archive/ask_archive.py said chatter_01 sourdough starter
python tools/archive/persona_preview.py chatter_01 5 --seed 7          # Markov persona, no model
python tools/archive/persona_rag_preview.py chatter_01 sourdough --seed 7   # retrieved examples, no model
```

[examples/README.md](examples/README.md) shows the exact output of these
commands on the synthetic log in `examples/sample-logs`. With the bot running,
`~markov <user>` posts a Markov line, and `~persona <user> [message]` asks the
model behind `[llm] endpoint` to answer in that chatter's voice. Live capture
(`[archive] live_capture`) keeps the archive growing while the bot runs.

## Which switch enables what

| Capability | Switch |
| --- | --- |
| Translation providers | `DEEPL_API_KEY` or `GOOGLE_APPLICATION_CREDENTIALS` in `.env`; thresholds under `[translation]` |
| Auto-translate | `~global_autotl`, `~chan_autotl`, `~autotl`, `~notranslate` at runtime (stored in the settings database) |
| Archive capture | `[archive] live_capture` |
| Markov personas | `[persona] mimic_enabled` |
| Model personas | `[llm] enabled` and `[llm] endpoint`; `~model off` and `~model on` at runtime |
| Unprompted persona reactions | `[persona] reaction_chance` (0 keeps the bot quiet) |
| Output denylist | `[persona] blocklist_file` |

## Docs, tests, license

- [Setup](docs/SETUP.md), [Commands](docs/COMMANDS.md),
  [Architecture](docs/ARCHITECTURE.md), [Chat archive](docs/CHAT_ARCHIVE.md),
  [Generation and bot modes](docs/GENERATE_AND_BOT_MODES.md),
  [Fine-tuning](docs/FINE_TUNING.md), [Research questions](docs/RESEARCH_QUESTIONS.md).
- Tests: `python -m unittest discover -s tests -q`, then
  `python tools/check/audit_commands.py` and `python tools/check/check_readme_commands.py`.
- Personas recombine real chat. Use them only on logs you are allowed to use,
  and keep `data/` private; it is gitignored.
- [MIT license](LICENSE). Developed with AI assistance in implementation,
  debugging and documentation; the design decisions are the author's.
