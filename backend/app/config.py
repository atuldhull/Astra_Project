import os
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_root() -> Path:
    """Root of every ASTRA data directory: weights, datasets, secrets, uploads.

    Point ASTRA_DATA_DIR at wherever you keep the big files. The default
    (~/astra-data) works on Windows, Linux and macOS without editing anything,
    so a fresh clone boots. ASTRA_DATA_ROOT is the older name, still honoured.
    """
    explicit = os.getenv("ASTRA_DATA_DIR") or os.getenv("ASTRA_DATA_ROOT")
    return Path(explicit) if explicit else Path.home() / "astra-data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Everything below defaults to a subdirectory of data_root. Set an
    # individual env var only when one directory lives somewhere unusual.
    data_root: Path = Field(
        default_factory=_default_data_root,
        validation_alias=AliasChoices("ASTRA_DATA_DIR", "ASTRA_DATA_ROOT"),
    )
    datasets_dir: Path | None = Field(default=None, alias="ASTRA_DATASETS_DIR")
    weights_dir: Path | None = Field(default=None, alias="ASTRA_WEIGHTS_DIR")
    runs_dir: Path | None = Field(default=None, alias="ASTRA_RUNS_DIR")
    tiles_dir: Path | None = Field(default=None, alias="ASTRA_TILES_DIR")
    uploads_dir: Path | None = Field(default=None, alias="ASTRA_UPLOADS_DIR")
    secrets_dir: Path | None = Field(default=None, alias="ASTRA_SECRETS_DIR")
    anchors_dir: Path | None = Field(default=None, alias="ASTRA_ANCHORS_DIR")
    models_dir: Path | None = Field(default=None, alias="ASTRA_MODELS_DIR")
    federated_dir: Path | None = Field(default=None, alias="ASTRA_FEDERATED_DIR")

    model_path: Path | None = Field(default=None, alias="ASTRA_MODEL_PATH")
    onnx_path: Path | None = Field(default=None, alias="ASTRA_ONNX_PATH")
    inference_device: str = Field(default="cuda:0", alias="ASTRA_INFERENCE_DEVICE")
    imgsz: int = Field(default=1024, alias="ASTRA_IMGSZ")
    conf_threshold: float = Field(default=0.25, alias="ASTRA_CONF_THRESHOLD")
    iou_threshold: float = Field(default=0.45, alias="ASTRA_IOU_THRESHOLD")

    backend_host: str = Field(default="127.0.0.1", alias="ASTRA_BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="ASTRA_BACKEND_PORT")
    secret_key: str = Field(default="change-me", alias="ASTRA_SECRET_KEY")

    postgres_host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="astra", alias="POSTGRES_DB")
    postgres_user: str = Field(default="astra", alias="POSTGRES_USER")
    postgres_password: str = Field(default="astra_dev", alias="POSTGRES_PASSWORD")

    redis_host: str = Field(default="127.0.0.1", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    # Demo "friendly force" locations used by threat scoring for proximity term.
    # Ordered by importance. Each entry: (name, lat, lon).
    # These anchor the map — if your AOI is elsewhere, override via .env FRIENDLY_ASSETS.
    friendly_assets_json: str = Field(
        default='[["FOB Delta", 12.9716, 77.5946], ["Outpost Bravo", 12.9750, 77.5900]]',
        alias="ASTRA_FRIENDLY_ASSETS",
    )

    @model_validator(mode="after")
    def _derive_paths(self) -> "Settings":
        root = self.data_root
        for attr, name in (
            ("datasets_dir", "datasets"),
            ("weights_dir", "weights"),
            ("runs_dir", "runs"),
            ("tiles_dir", "tiles"),
            ("uploads_dir", "uploads"),
            ("secrets_dir", "secrets"),
            ("anchors_dir", "anchors"),
            ("models_dir", "models"),
            ("federated_dir", "federated"),
        ):
            if getattr(self, attr) is None:
                setattr(self, attr, root / name)
        if self.model_path is None:
            self.model_path = self.weights_dir / "astra-v1.pt"
        if self.onnx_path is None:
            self.onnx_path = self.weights_dir / "astra-v1.onnx"
        return self

    @property
    def friendly_assets(self) -> list[tuple[str, float, float]]:
        import json
        try:
            data = json.loads(self.friendly_assets_json)
            return [(str(n), float(la), float(lo)) for n, la, lo in data]
        except Exception:
            return []

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()

# Module-level aliases so callers never have to rebuild these paths by hand.
# Import these instead of hardcoding a data directory anywhere.
DATA_ROOT: Path = settings.data_root
DATASETS_DIR: Path = settings.datasets_dir
WEIGHTS_DIR: Path = settings.weights_dir
RUNS_DIR: Path = settings.runs_dir
TILES_DIR: Path = settings.tiles_dir
UPLOADS_DIR: Path = settings.uploads_dir
SECRETS_DIR: Path = settings.secrets_dir
ANCHORS_DIR: Path = settings.anchors_dir
MODELS_DIR: Path = settings.models_dir
FEDERATED_DIR: Path = settings.federated_dir
FEDERATED_LOG: Path = FEDERATED_DIR / "run.jsonl"
