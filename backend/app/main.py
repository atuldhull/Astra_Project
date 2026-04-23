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
