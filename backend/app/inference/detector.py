"""
Thin wrapper around Ultralytics YOLO. Lazy-loaded so the backend can boot
even before the trained weights exist (useful during Day 1-2 of the build).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.config import settings

_model = None
_model_lock = Lock()


CLASS_NAMES = [
    "small-vehicle",
    "large-vehicle",
    "aircraft-fixed-wing",
    "aircraft-rotor",
    "ship",
    "storage-depot",
    "harbor",
    "bridge",
]


@dataclass(frozen=True)
class DetectionRecord:
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    track_id: int | None = None  # populated for video tracking, None for single-image detect()


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from ultralytics import YOLO

        path = settings.model_path
        if not Path(path).exists():
            raise FileNotFoundError(
                f"Model weights not found at {path}. "
                "Train first: python training/train.py --config training/configs/astra-v1.yaml"
            )
        _model = YOLO(str(path))
    return _model


def is_ready() -> bool:
    return Path(settings.model_path).exists()


def detect(image_bgr, imgsz: int | None = None, conf: float | None = None) -> list[DetectionRecord]:
    """Run detection on a single BGR image (numpy ndarray H×W×3).
    Returns an empty list if the model isn't loaded yet and is_ready() is False —
    callers can probe is_ready() first to distinguish 'no detections' from 'no model'.
    """
    if not is_ready():
        return []
    model = _load_model()
    results = model.predict(
        image_bgr,
        imgsz=imgsz or settings.imgsz,
        conf=conf if conf is not None else settings.conf_threshold,
        iou=settings.iou_threshold,
        device=settings.inference_device,
        verbose=False,
    )
    out: list[DetectionRecord] = []
    if not results:
        return out
    r = results[0]
    if r.boxes is None:
        return out
    xyxy = r.boxes.xyxy.cpu().numpy()
    conf_arr = r.boxes.conf.cpu().numpy()
    cls_arr = r.boxes.cls.cpu().numpy().astype(int)
    for (x1, y1, x2, y2), c, k in zip(xyxy, conf_arr, cls_arr, strict=True):
        name = CLASS_NAMES[k] if 0 <= k < len(CLASS_NAMES) else str(k)
        out.append(DetectionRecord(int(k), name, float(c), float(x1), float(y1), float(x2), float(y2)))
    return out


def detect_and_track_video(
    video_path: str,
    max_frames: int = 30,
    vid_stride: int = 1,
):
    """For video paths: stream frames through YOLO+ByteTrack and yield
    (frame_index, timestamp_ms, frame_bgr, detections_with_track_ids).

    Uses Ultralytics' built-in tracking (persist=True maintains tracker state
    across frames within a single call). track_id is stable across frames for
    the same object. Stops after max_frames yields to cap demo latency.

    Yields:
        frame_index: 0-based index into the INPUT video (accounts for stride)
        timestamp_ms: milliseconds into the video
        frame_bgr: numpy H×W×3 BGR image (the original frame)
        records: list[DetectionRecord] with track_id populated
    """
    if not is_ready():
        return
    model = _load_model()

    # Probe FPS so we can report real timestamps back to callers
    import cv2  # local import keeps import-time footprint small
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    cap.release()

    # Auto-stride: if video has too many frames, skip to keep within max_frames
    if total_frames > 0 and vid_stride == 1:
        vid_stride = max(1, total_frames // max_frames)

    results_gen = model.track(
        source=video_path,
        stream=True,
        persist=True,
        tracker="bytetrack.yaml",
        conf=settings.conf_threshold,
        iou=settings.iou_threshold,
        imgsz=settings.imgsz,
        device=settings.inference_device,
        vid_stride=vid_stride,
        verbose=False,
    )

    yielded = 0
    for i, result in enumerate(results_gen):
        if yielded >= max_frames:
            break
        frame = result.orig_img
        if frame is None:
            continue
        actual_frame_idx = i * vid_stride
        ts_ms = int(round(actual_frame_idx / fps * 1000))

        records: list[DetectionRecord] = []
        if result.boxes is not None and len(result.boxes) > 0:
            xyxy = result.boxes.xyxy.cpu().numpy()
            conf_arr = result.boxes.conf.cpu().numpy()
            cls_arr = result.boxes.cls.cpu().numpy().astype(int)
            # .id is None on the first frame (tracker initializes) and when 0 detections
            ids = (
                result.boxes.id.cpu().numpy().astype(int)
                if result.boxes.id is not None
                else [None] * len(xyxy)
            )
            for (x1, y1, x2, y2), c, k, tid in zip(xyxy, conf_arr, cls_arr, ids, strict=True):
                name = CLASS_NAMES[k] if 0 <= k < len(CLASS_NAMES) else str(k)
                records.append(DetectionRecord(
                    class_id=int(k),
                    class_name=name,
                    confidence=float(c),
                    x1=float(x1), y1=float(y1),
                    x2=float(x2), y2=float(y2),
                    track_id=int(tid) if tid is not None else None,
                ))

        yield actual_frame_idx, ts_ms, frame, records
        yielded += 1
