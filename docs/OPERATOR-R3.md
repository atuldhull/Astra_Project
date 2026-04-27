# ASTRA Round-3 — Operator Runbook

> Five things only YOU can do. Each is independent — run zero or all. The
> R3 codebase ships fine without any of them; they unlock specific demo
> moments.

---

## F2 — Telegram bot (~10 minutes, dramatic demo moment)

Adds the "phone buzzes on stage" moment to the demo.

1. Open Telegram. Start a chat with `@BotFather`. Send `/newbot`. Give it a name like `astra-cmdr-bot`. BotFather replies with a token — copy it.
2. Open a new chat with your fresh bot and send any message.
3. In a browser, open: `https://api.telegram.org/bot<TOKEN>/getUpdates`. Find `chat.id` in the JSON.
4. Add to `.env` at the repo root:
   ```
   TELEGRAM_BOT_TOKEN=<your-token>
   TELEGRAM_CHAT_ID=<your-chat-id>
   TELEGRAM_ALERT_THRESHOLD=0.85
   ```
5. Restart the backend.
6. Test: ingest any high-threat image on the Mission page. Phone should buzz with a markdown alert.

---

## F5 — TensorRT INT8 export (~30 min on operator's GPU machine)

Adds a 3rd benchmark number to the slides ("Edge INT8: X ms / FPS").

```
cd /c/Users/atuld/OneDrive/Desktop/astra
D:/astra-data/venvs/astra/Scripts/python.exe training/export_tensorrt.py --int8
```
- Auto-falls back to FP16 if INT8 calibration fails (still a 3rd number).
- Output: `D:/astra-data/weights/astra-v1.engine` + 50-run latency report.
- Engine isn't portable — must run on the deployment device.

---

## F1 — PGD adversarial training (~2-4 hours on operator's GPU)

Replaces the partial-defense FGSM-augmentation hardened model with real
PGD adversarial training. Should bring helipad-style wins to all 5 demo
images, not just one.

```
D:/astra-data/venvs/astra/Scripts/python.exe training/pgd_finetune.py \
    --weights D:/astra-data/runs/astra-v1-2/weights/best.pt \
    --epochs 5 --eps 0.03 --pgd-steps 3
```
- 50% of each batch is adversarially perturbed against the *current*
  model (not a frozen baseline).
- After: `cp D:/astra-data/runs/astra-v1-pgd/weights/best.pt D:/astra-data/weights/astra-v1-hardened.pt`
- Adversarial page picker auto-detects on next request.

---

## F8 — MAR20 cls federated training (~1 hour on GPU)

Replaces the synthetic-task federated demo with a real MAR20 federated
training run. Same FoolsGold, same dashboard panels — just real numbers.

```
# 1. Partition the MAR20 train set into 3 disjoint client folders:
D:/astra-data/venvs/astra/Scripts/python.exe federated/partition.py --mode non-iid

# 2. Run federated training:
D:/astra-data/venvs/astra/Scripts/python.exe -m federated.run_demo \
    --task mar20 --partition-root D:/astra-data/datasets/mar20-cls-fed \
    --rounds 5 --device cuda
```

---

## F6 — RAG commander Q&A LLM upgrade (~10 min download)

Backend ships with a rule-based Q&A fallback that's already wired to the
new `/chat` page. To upgrade to natural-language responses with retrieval:

1. Install: `pip install llama-cpp-python`
2. Download a Phi-3.5-mini-instruct GGUF (~2.4 GB) — e.g. from HuggingFace,
   `microsoft/Phi-3.5-mini-instruct-gguf`, the `Q4_K_M` quant.
3. Drop the file at: `D:/astra-data/models/phi-3.5-mini-instruct.Q4_K_M.gguf`
4. Restart the backend. Chat page header pill changes from `rule-based` to
   `Phi-3.5 LLM` automatically.

If the model isn't there or llama-cpp-python isn't installed, the rule-
based path still answers ~12 canonical question shapes — pre-tested.

---

## F16 — YAMNet audio drone-detection (DEFERRED)

Kept in the v3+ roadmap. Adds a "phone-mic listening for drone propellers
+ confirms with vision" multi-modal alert. Not needed for the trophy demo;
the visual cascade does the heavy lifting.

If you want to implement: download YAMNet TFLite, integrate via tflite-
runtime, add an audio sidecar to the pipeline. ~8 hours of work.

---

## Continual learning (operator-cron, optional)

Ships with operator-confirmed alerts → nightly fine-tune queue:
```
D:/astra-data/venvs/astra/Scripts/python.exe training/continual_finetune.py
D:/astra-data/venvs/astra/Scripts/python.exe training/train.py --config training/configs/astra-v1-continual.yaml
```
Schedule via Windows Task Scheduler / cron for nightly runs.

---

## Final pre-demo check

```
docker ps | grep astra-       # both healthy?
D:/astra-data/venvs/astra/Scripts/python.exe backend/scripts/init_db.py
D:/astra-data/venvs/astra/Scripts/python.exe scripts/e2e_regression.py
```
ALL GREEN = ship-ready.
