"""ASTRA federated learning package.

Three simulated forward operating bases each train on geographically disjoint
DOTA-derived data; an aggregator runs FedAvg with FoolsGold poison detection.
The whole thing runs on one machine via multiprocess in run_demo.py — no
network setup needed for the demo.

Modules:
  foolsgold  — pure-NumPy Sybil detector (cosine-similarity reweighting)
  strategy   — Flower strategy = FedAvg + FoolsGold + per-round mAP logging
  client     — Flower NumPyClient wrapping a configurable PyTorch model
  server     — entrypoint that starts the Flower server with our strategy
  task       — small CNN + dataloaders (MAR20 cls if available, synthetic else)
  partition  — split a dataset into N IID/non-IID disjoint client subsets
  run_demo   — orchestrates 1 server + 3 clients in subprocesses
  log        — tiny JSONL telemetry sink consumed by /api/v1/federated
"""
