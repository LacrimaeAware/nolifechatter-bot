# NoLifeChatter

A Twitch translation bot with language practice, chat history tools,
local model personas and embedding-based analysis.

- **Model personas:** `~persona` asks a local model to reply in a chosen chatter's
  style, using retrieved writing examples, topic matches and conversation
  snippets. Candidate replies are checked for copying and ranked for context
  and writing style. `~generate`
  combines chatters, traits and topics; channel personas can respond to mentions
  or ordinary chat.
- **Archive questions:** `~askchat` retrieves passages and supplies them to the
  model, with source labels. Author-scoped questions can combine keyword and
  embedding rankings. Raw mode returns the evidence without generating an answer.
- **Embedding analysis:** `~vibes` finds chatters with similar topics and language
  using person vectors. `~twin` combines
  vector similarity with word and emote use, and trait commands compare vectors
  with text-defined scales. Building the vectors requires an embedding model.
- **Translation and archive tools:** translate through DeepL or Google Cloud
  Translation, practise languages through whispers, import Chatterino logs,
  search phrases and retrieve quotes. Markov generation is also available
  without a model.

The bot replies to commands in the channels it joins. The archive tools can
also run offline, without Twitch or a model server.

[Project page](https://lacrimaeaware.github.io/nolifechatter-bot/) · [Model personas](docs/GENERATE_AND_BOT_MODES.md)
· [Indexes and analysis](docs/ARCHITECTURE.md#analysis-data-files)
· [Optional LoRA training](docs/FINE_TUNING.md)

## Run the bot

Requires Python 3.12 or newer and a Twitch account and application for the bot.
Translation also needs
a DeepL API key or Google Cloud Translation credentials. See
[Setup](docs/SETUP.md) for provider configuration and OAuth.

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
`~setlang ES`, `~practice on es,ja en`.

## Try the archive offline

After installing dependencies, copy `config.example.toml` to `config.toml`.
These commands use invented chat logs and need no Twitch or model connection:

```sh
python tools/archive/ingest_chatterino.py examples/sample-logs
python tools/archive/ask_archive.py said chatter_01 sourdough starter
python tools/archive/persona_rag_preview.py chatter_01 sourdough --seed 7
```

[examples/README.md](examples/README.md) shows the output of these commands.
The retrieval preview prints selected messages using keyword search by default.

With a model server and the bot running, `~persona <user> [message]` asks the
model at `[llm] endpoint` to answer in that chatter's style. Set
`[archive] live_capture` to save new messages while the bot runs.

## Settings

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
- Runtime data is stored in the gitignored `data/` folder.
- [MIT license](LICENSE) · [Project and dependency notes](PROVENANCE.md).

## Build the project page

Build the static site:

```sh
python -m pip install -r tools/build/requirements-site.txt
python tools/build/build_site.py
```

Serve the generated page locally:

```sh
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

Open `http://127.0.0.1:8000`. The generated `site/` folder is a standalone
static site.

For GitHub Pages, set **Settings → Pages → Build and deployment → Source** to
**GitHub Actions**. The **Publish project page** workflow builds and deploys
`site/` on pushes to `main`, or through **Actions → Publish project page → Run workflow**.
