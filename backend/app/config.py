from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_root: Path = Field(default=Path("D:/astra-data"), alias="ASTRA_DATA_ROOT")
    datasets_dir: Path = Field(default=Path("D:/astra-data/datasets"), alias="ASTRA_DATASETS_DIR")
    weights_dir: Path = Field(default=Path("D:/astra-data/weights"), alias="ASTRA_WEIGHTS_DIR")
    runs_dir: Path = Field(default=Path("D:/astra-data/runs"), alias="ASTRA_RUNS_DIR")
    tiles_dir: Path = Field(default=Path("D:/astra-data/tiles"), alias="ASTRA_TILES_DIR")
    uploads_dir: Path = Field(default=Path("D:/astra-data/uploads"), alias="ASTRA_UPLOADS_DIR")

    model_path: Path = Field(default=Path("D:/astra-data/weights/astra-v1.pt"), alias="ASTRA_MODEL_PATH")
    onnx_path: Path = Field(default=Path("D:/astra-data/weights/astra-v1.onnx"), alias="ASTRA_ONNX_PATH")
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
