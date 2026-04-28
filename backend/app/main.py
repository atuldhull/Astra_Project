from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.api import ws_router
from app.config import settings
from app.inference import detector

app = FastAPI(
    title="ASTRA",
    description="Aerial Surveillance & Threat Recognition Assistant",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(ws_router)


@app.on_event("startup")
async def warmup() -> None:
    """Pre-load every heavyweight model into memory at boot so the first
    user request isn't a 1-4s cold start.

    Each loader is wrapped in its own try/except so a missing weight file
    cannot prevent the server from starting — the rest of the app is
    still useful, and the operator may not have run training yet.
    """
    import time

    started = time.perf_counter()
    print("[warmup] start", flush=True)

    # Stage-1 detector
    try:
        if detector.is_ready():
            detector._load_model("v1")  # noqa: SLF001 — warmup intentionally touches private
            print("[warmup] detector v1 ready", flush=True)
        else:
            print("[warmup] detector v1 weights missing -- skipped", flush=True)
    except Exception as exc:  # noqa: BLE001 — startup never fails
        print(f"[warmup] detector load failed: {exc!r}", flush=True)

    # Stage-2 cascade (lazy import — module pulls Ultralytics only when needed)
    try:
        from app.inference import aircraft_classifier as cascade
        if cascade.is_ready():
            cascade._load_model()  # noqa: SLF001
            print("[warmup] cascade ready", flush=True)
        else:
            print("[warmup] cascade weights absent -- skipped", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[warmup] cascade load failed: {exc!r}", flush=True)

    # Phi-3.5 LLM (only if installed + GGUF present)
    try:
        from app.services.rag import _llm_available, _get_llm  # type: ignore
        if _llm_available():
            _get_llm()
            print("[warmup] Phi-3.5 LLM ready", flush=True)
        else:
            print("[warmup] Phi-3.5 LLM not available -- skipped", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[warmup] LLM load failed: {exc!r}", flush=True)

    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"[warmup] done in {elapsed_ms:.0f}ms", flush=True)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "device": settings.inference_device,
        "model_path": str(settings.model_path),
        "model_loaded": detector.is_ready(),
    }


@app.get("/")
def root() -> dict:
    return {"name": "ASTRA", "docs": "/docs"}
