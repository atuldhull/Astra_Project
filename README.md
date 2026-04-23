# ASTRA — Aerial Surveillance & Threat Recognition Assistant

Sovereign, offline-capable AI platform for military asset detection on drone/satellite imagery. Built for the **ASTRA Defence-Tech event, BMSIT&M Bengaluru**.

> **Full specification:** see [PROJECT_SPEC.md](PROJECT_SPEC.md). Read it before writing any code.

## Quick start

### Prerequisites (already verified on target machine)
- Windows 11, Python 3.13 (via `py` launcher), Node 22+, Docker Desktop 29+, Git
- NVIDIA GPU with CUDA 12.x+ driver (confirmed: RTX 4050 6GB, driver 581.83)

### One-time setup

1. **Create the data directory** (keep datasets and weights OUT of OneDrive):
   ```bash
   mkdir D:\astra-data
   mkdir D:\astra-data\datasets D:\astra-data\weights D:\astra-data\runs D:\astra-data\tiles D:\astra-data\uploads
   ```

2. **Copy env config:**
   ```bash
   cp .env.example .env
   ```

3. **Python env + deps** (in Git Bash). The venv lives **outside** OneDrive to avoid sync bloat:
   ```bash
   py -3.13 -m venv /d/astra-data/venvs/astra
   . /d/astra-data/venvs/astra/Scripts/activate
   pip install --upgrade pip
   pip install -r backend/requirements-cuda.txt   # PyTorch CUDA wheels (~2GB)
   pip install -r backend/requirements.txt        # everything else
   ```

4. **Verify CUDA is visible to PyTorch:**
   ```bash
   python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
   ```
   Expected: `CUDA: True | Device: NVIDIA GeForce RTX 4050 Laptop GPU`

5. **Frontend:**
   ```bash
   cd frontend
   npm install
   ```

6. **Infra (Postgres + Redis):**
   ```bash
   docker compose up -d
   ```

## Daily workflow

| Task | Command |
|---|---|
| Start backend | `. /d/astra-data/venvs/astra/Scripts/activate && cd backend && uvicorn app.main:app --reload` |
| Start frontend | `cd frontend && npm run dev` |
| Train model | `cd training && python train.py --config configs/astra-v1.yaml` |
| Convert DOTA → YOLO | `cd training && python prepare_dota.py` |
| Export ONNX | `cd training && python export_onnx.py` |
| Benchmark | `cd training && python benchmark.py` |

## Layout

```
astra/
├── PROJECT_SPEC.md    ← source of truth; read first
├── backend/           ← FastAPI + inference workers
├── frontend/          ← React + Vite + Leaflet
├── training/          ← dataset prep, training, export
├── scripts/           ← one-off utilities
├── docs/              ← generated reports, demo script
└── docker-compose.yml ← Postgres + Redis only
```

Data lives outside the repo at `D:\astra-data\` (see [.env.example](.env.example)).
