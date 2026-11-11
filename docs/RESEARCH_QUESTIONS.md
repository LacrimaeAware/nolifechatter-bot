# Archive experiments and research questions

Proposed evaluations of existing bot components.

| Question | Existing component | Comparison | Evaluation |
|---|---|---|---|
| When does dense retrieval improve chat-history answers? | `utils/archive_qa.py`, `utils/persona_msg_index.py` | FTS5 alone, dense retrieval alone, and the combined retrieval path with the same context budget. | Recall of annotated source messages, citation support and answer accuracy on held-out questions. |
| Does chronological context help resolve short or ambiguous messages? | Archive windows and context assembly in `utils/chat_archive.py` and `utils/archive_qa.py`. | Retrieved messages alone versus matched preceding/following windows. | Separate questions needing conversation context from keyword lookups; report accuracy and added context tokens. |
| How much authorship prediction comes from topic rather than writing style? | TF-IDF/logistic regression in `utils/persona_classifier.py`. | Random splits versus time-separated and channel-separated splits; remove names and repeated quotes. | Macro-F1, calibration and confusion matrices, with majority and simple vocabulary baselines. |
| Which retrieval choices preserve a requested style without copying source lines? | `utils/persona_llm.py` and `utils/persona_generate.py`. | Random examples, distinctive examples and topic-matched examples using the same model and prompt budget. | Blinded ratings from consenting participants, source overlap and task relevance. |
| How does the model queue behave under bursts? | `services/model_queue.py`. | Fixed synthetic request workloads with timeouts, cancellations and model-off transitions. | Queue wait, completion time, cancellation behavior and interference with non-model commands. |

## Archive retrieval study

One proposed study uses a small invented conversation set with
known answers and supporting message IDs. Include direct lookup, paraphrase,
conversation-context and unanswerable questions. Hold the question set fixed
before tuning retrieval, and save each retrieved context and response.

## Interpreting analysis scores

Authorship similarity scores compare messages; they do not verify a person's
identity. Trait scores describe patterns in text and have not been validated
as psychological measurements.

[Project overview](../README.md) · [Archive schema](CHAT_ARCHIVE.md) · [Command reference](COMMANDS.md)
