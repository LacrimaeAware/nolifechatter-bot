# Archive experiments and research questions

These are proposed evaluations of implemented components. The table defines
what to test; it does not report completed benchmark results.

| Question | Existing component | Comparison | Evaluation |
|---|---|---|---|
| When does dense retrieval improve chat-history answers? | `utils/archive_qa.py`, `utils/persona_msg_index.py` | FTS5 alone, dense retrieval alone, and the combined retrieval path with the same context budget. | Recall of annotated source messages, citation support and answer accuracy on held-out questions. |
| Does chronological context help resolve short or ambiguous messages? | Archive windows and context assembly in `utils/chat_archive.py` and `utils/archive_qa.py`. | Retrieved messages alone versus matched preceding/following windows. | Separate questions needing conversation context from keyword lookups; report accuracy and added context tokens. |
| How much authorship prediction comes from topic rather than writing style? | TF-IDF/logistic regression in `utils/persona_classifier.py`. | Random splits versus time-separated and channel-separated splits; remove names and repeated quotes. | Macro-F1, calibration and confusion matrices, with majority and simple vocabulary baselines. |
| Which retrieval choices preserve a requested style without copying source lines? | `utils/persona_llm.py` and `utils/persona_generate.py`. | Random examples, distinctive examples and topic-matched examples using the same model and prompt budget. | Blinded ratings from consenting participants, source overlap and task relevance. |
| How does the model queue behave under bursts? | `services/model_queue.py`. | Fixed synthetic request workloads with timeouts, cancellations and model-off transitions. | Queue wait, completion time, cancellation behavior and interference with non-model commands. |

## A useful first study

Start with archive retrieval. Build a small synthetic conversation set with
known answers and supporting message IDs. Include direct lookup, paraphrase,
conversation-context and unanswerable questions. Hold the question set fixed
before tuning retrieval, and save each retrieved context and response.

This produces a runnable evaluation of a central bot component without
requiring a live stream or publishing chat logs. A later permissioned dataset
could test whether the result transfers to real conversations.

## Project boundaries

- The runtime bot handles translation, commands, settings and live operation.
- The archive layer handles storage, search and retrieval.
- Research experiments compare those components under stated conditions.
- Fine-tuning is an optional offline path with its own data and evaluation needs.

These can remain directories within one repository until their dependency and
release needs justify separate packages. Public examples should use synthetic
or permissioned data. Authorship similarity is not identity verification, and
text-derived trait scores are not validated psychological measurements.

[Project overview](../README.md) · [Archive schema](CHAT_ARCHIVE.md) · [Command reference](COMMANDS.md)
