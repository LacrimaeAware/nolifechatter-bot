# Fine-tuning a persona voice model

This optional workflow trains a LoRA to adapt a model's writing style to the
chat messages in your logs, then runs the merged model locally in LM Studio.
Retrieval supplies archived messages in the prompt; fine-tuning changes model
weights. The bot's persona commands also work with an untuned local model.

Scripts in `experiments/finetune/`:

| File | Runs where | Does |
| --- | --- | --- |
| `export_persona_sft.py` | your machine | turns the archive into chat-format training data |
| `RUN_ME_ON_RUNPOD.sh` | rented GPU | entry point; calls the script below |
| `runpod_train_persona_lora.sh` | rented GPU | creates the environment, installs Unsloth, trains, zips the adapter |
| `train_persona_lora_unsloth.py` | rented GPU | the training loop (LoRA/QLoRA with Unsloth and TRL) |
| `runpod_merge_lora_to_gguf.sh` | rented GPU | merges the adapter into the base model and exports a quantized GGUF |

## 1. Export training data

```powershell
.\.venv\Scripts\python.exe experiments\finetune\export_persona_sft.py `
  --channels yourchannel `
  --authors user1,user2,user3 `
  --user-aliases altaccount=user1 `
  --exclude-users nightbot,yourbotaccount `
  --max-examples-per-author 5000
```

Output files (gitignored):

- `data/unsynced/fine_tune/persona_train.jsonl`
- `data/unsynced/fine_tune/persona_val.jsonl`

Each row is OpenAI-style chat JSONL: a fixed `system` instruction, a `user`
turn with `<persona=name>` plus the preceding chat context, and the real next
message that persona wrote as the `assistant` turn. Training is supervised
next-token prediction on the assistant turn (completion-only loss when the
installed TRL supports it).

Bundle the data with the three GPU-side files:

```powershell
.\.venv\Scripts\python.exe -c "import zipfile; z = zipfile.ZipFile('data/unsynced/fine_tune/persona_sft_runpod.zip', 'w', zipfile.ZIP_DEFLATED); [z.write(p, p.split('/')[-1]) for p in ['data/unsynced/fine_tune/persona_train.jsonl', 'data/unsynced/fine_tune/persona_val.jsonl', 'experiments/finetune/RUN_ME_ON_RUNPOD.sh', 'experiments/finetune/runpod_train_persona_lora.sh', 'experiments/finetune/train_persona_lora_unsloth.py']]; z.close()"
```

The zip is flat: the shell scripts expect `persona_train.jsonl`,
`persona_val.jsonl` and `train_persona_lora_unsloth.py` next to them.

## 2. Train on a rented GPU

Upload `persona_sft_runpod.zip` to `/workspace/` on the pod (Jupyter file
browser), then in the pod terminal:

```bash
cd /workspace
rm -rf nlc_persona
python -m zipfile -e persona_sft_runpod.zip nlc_persona
bash nlc_persona/RUN_ME_ON_RUNPOD.sh
```

The base model and its end-of-sequence token are environment variables; the
default is a Llama 3.1 8B instruct variant with `<|eot_id|>`. The EOS token
must match the base family or completion masking breaks:

```bash
MODEL=huihui-ai/Qwen2.5-7B-Instruct-abliterated EOS_TOKEN='<|im_end|>' bash nlc_persona/RUN_ME_ON_RUNPOD.sh
```

Checkpoints are saved under `/workspace/nlc_persona/persona_lora` every 100
optimizer steps and the script resumes from the newest `checkpoint-*` folder,
so an interrupted run continues with the same command. When it finishes,
download `/workspace/nlc_persona/persona_lora_result.zip` (the adapter) and
stop the pod unless you merge next.

## 3. Merge to GGUF for LM Studio

LM Studio loads GGUF files, not PEFT adapters. On the same pod (the base model
is already cached), upload `runpod_merge_lora_to_gguf.sh` into
`/workspace/nlc_persona/` and run it:

```bash
cd /workspace/nlc_persona
bash runpod_merge_lora_to_gguf.sh
```

It merges the adapter into the base weights, converts with llama.cpp and
quantizes to `persona_merged_Q4_K_M.gguf` (override `ADAPTER`, `BASE`, `OUT`,
`QUANT` through the environment). Download the GGUF, put it in LM Studio's
models folder, load it, and terminate the pod.

## 4. Use and compare

- Serve the merged model in LM Studio and set `[llm] model` to its id, or add
  a shortcut under `[llm] model_shortcuts` so `~persona model=lora chatter_01 <message>`
  picks it per call.
- `[llm] ab_models = ["<base id>", "<lora id>"]` rolls one model per
  generation and tags posted lines `#llama` or `#lora`, so chat judges the
  candidates in place.
- `experiments/eval/compare_models.py --models <base id>,<lora id>` generates
  samples with the same author, channel and mode settings on both models, then
  scores each line with the authorship classifier (`tools/build/train_classifier.py`
  builds it). Retrieval and context can differ between calls.
- `experiments/eval/eval_personas.py` compares generated-line classifier attribution
  with sampled archive lines. `eval_heldout_replies.py` compares generated replies
  with held-out replies and their preceding context.

## GPU and training shape

- Defaults in `train_persona_lora_unsloth.py`: 1 epoch, rank 16, learning rate
  2e-4, sequence length 2048, effective batch 16 (`batch_size=2`,
  `grad_accum=8`), 5% validation split from the exporter, checkpoint every 100
  steps. A pilot of 41k training rows took about 2,580 optimizer steps at
  roughly 2.4 s per step on an RTX 4090.
- A Network Volume mounted at `/workspace` preserves caches, checkpoints and
  the adapter across pod restarts.

## Troubleshooting

- `unzip: command not found`: use `python -m zipfile -e` as above.
- `evaluation_strategy` / `eval_strategy` errors: handled in the training
  script by checking the installed Transformers and TRL signatures.
- `fp16` versus `bf16`: the script detects CUDA bf16 support and uses bf16 on
  Ampere and newer cards.
- `.nfs... Device or resource busy` during tokenization: temporary files on a
  Network Volume; the wrapper keeps temp files under `/tmp` and limits dataset
  preprocessing to one worker.
- `Ctrl+C` before the first checkpoint loses the run; after step 100 a rerun
  resumes.

## Output filtering

Generated messages pass through `utils/output_filter.py` before they are
posted. The configured denylist is stored in `data/unsynced/blocklist.txt`.
