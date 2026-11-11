# NoLifeChatter

A Twitch bot for translation, language practice and replies in a chosen
chatter's style.

[Project page](https://lacrimaeaware.github.io/nolifechatter-bot/)

- **Translation:** DeepL or Google Cloud translates messages between languages;
  practice mode sends study-language translations through whispers and native-language
  translations back to the channel.
- **Persona replies:** a local model receives writing examples from a chatter's
  history, related messages and the current conversation. Candidate replies are
  checked for copying and ranked for relevance and style.
- **Archive questions:** keyword and embedding retrieval select saved passages for
  questions about the chat history. Raw mode shows the matching messages.

## Persona context example

`~persona chatter_01 sourdough` selects a conversation about sourdough and other
writing examples from the same chatter.
[The walkthrough](examples/README.md#preview-the-messages-selected-for-a-model-reply)
shows the selected passages from fictional chat logs.

## Reference

- [Bot setup and requirements](docs/SETUP.md)
- [Commands](docs/COMMANDS.md) · [Generation and channel modes](docs/GENERATE_AND_BOT_MODES.md)
- [Architecture and build commands](docs/ARCHITECTURE.md) · [Archive format](docs/CHAT_ARCHIVE.md)
- [Model fine-tuning](docs/FINE_TUNING.md) · [Analysis readouts](docs/RESEARCH_QUESTIONS.md)
- [Project and dependency notes](PROVENANCE.md) · [MIT license](LICENSE)
