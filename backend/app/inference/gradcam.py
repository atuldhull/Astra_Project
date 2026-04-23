"""
Explainability via EigenCAM for YOLO detections.

Given an image and (optionally) a detection bbox, returns a PNG showing
the model's spatial attention heatmap overlaid on the image. Uses EigenCAM
(gradient-free, PCA on activations) because it's robust to YOLO's custom
output structure — standard Grad-CAM needs a classification-style logit that
YOLO doesn't expose directly.

Target layer: the C2PSA block (index 10 in YOLO11n), which is the last
backbone-level feature map before the FPN neck. 20×20 spatial resolution at
640² input — coarse but semantically rich, visually clear after up-sampling.
"""

from __future__ import annotations

from threading import Lock

import cv2
import numpy as np

_target_layer = None
_layer_lock = Lock()


def _letterbox(image_bgr: np.ndarray, imgsz: int = 640) -> tuple[np.ndarray, float, int, int]:
    """Resize + pad to (imgsz, imgsz) keeping aspect ratio. Returns
    (padded_rgb_float_hwc, scale, pad_x, pad_y)."""
    h, w = image_bgr.shape[:2]
    r = min(imgsz / h, imgsz / w)
    new_w, new_h = int(round(w * r)), int(round(h * r))
    pad_w = (imgsz - new_w) // 2
    pad_h = (imgsz - new_h) // 2

    resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    padded = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    padded[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    return rgb.astype(np.float32) / 255.0, r, pad_w, pad_h


def _get_target_layer(yolo_model):
    """Resolve the layer to extract activations from. Cached."""
    global _target_layer
    with _layer_lock:
        if _target_layer is not None:
            return _target_layer
        inner = yolo_model.model  # DetectionModel (nn.Module)
        inner.eval()
        try:
            _target_layer = inner.model[10]  # C2PSA for YOLO11n
        except (AttributeError, IndexError, TypeError):
            modules = list(inner.model)  # type: ignore[attr-defined]
            _target_layer = modules[-2]
    return _target_layer


def _eigencam_heatmap(activations: np.ndarray) -> np.ndarray:
    """Classic EigenCAM: SVD of (C, H*W) activations — the dominant singular
    vector over spatial positions is the heatmap. Gradient-free, fast."""
    c, h, w = activations.shape
    flat = activations.reshape(c, h * w)
    flat_centered = flat - flat.mean(axis=1, keepdims=True)
    # economy SVD on a (C, H*W) matrix — Vt[0] is the dominant right sing. vec
    _, _, vt = np.linalg.svd(flat_centered, full_matrices=False)
    heatmap = vt[0].reshape(h, w)
    heatmap = np.abs(heatmap)
    hmin, hmax = heatmap.min(), heatmap.max()
    return (heatmap - hmin) / (hmax - hmin + 1e-8)


def compute_heatmap_png(
    yolo_model,
    image_bgr: np.ndarray,
    box_xyxy: tuple[float, float, float, float] | None = None,
    imgsz: int = 640,
    alpha: float = 0.55,
) -> bytes:
    """Render a heatmap over `image_bgr` and return PNG bytes.

    If `box_xyxy` is given in original-image pixel coords, the heatmap
    intensity is dampened outside the box (with a soft Gaussian falloff)
    so the visualization visibly focuses on that detection.
    """
    import torch

    target_layer = _get_target_layer(yolo_model)
    inner = yolo_model.model
    inner.eval()

    rgb_norm, _, pad_x, pad_y = _letterbox(image_bgr, imgsz=imgsz)
    input_tensor = torch.from_numpy(rgb_norm).permute(2, 0, 1).unsqueeze(0).contiguous()
    device = next(inner.parameters()).device
    input_tensor = input_tensor.to(device)

    # Forward pass with hook capturing the target layer's activations.
    captured: list = []

    def _hook(_module, _inp, out):
        captured.append(out.detach())

    h = target_layer.register_forward_hook(_hook)
    try:
        with torch.no_grad():
            _ = inner(input_tensor)
    finally:
        h.remove()

    if not captured:
        raise RuntimeError("no activations captured — target layer may not have fired")
    acts = captured[0][0].float().cpu().numpy()  # (C, H, W) for batch=1
    heatmap_small = _eigencam_heatmap(acts)

    # Upsample to letterboxed size
    heatmap_letterboxed = cv2.resize(heatmap_small, (imgsz, imgsz), interpolation=cv2.INTER_LINEAR)

    # Undo letterbox: crop out the padding region, then resize to original.
    h_end = imgsz - pad_y if pad_y > 0 else imgsz
    w_end = imgsz - pad_x if pad_x > 0 else imgsz
    heatmap_inner = heatmap_letterboxed[pad_y:h_end, pad_x:w_end]

    orig_h, orig_w = image_bgr.shape[:2]
    heatmap = cv2.resize(heatmap_inner, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

    # Focus on box if provided (soft mask).
    if box_xyxy is not None:
        x1, y1, x2, y2 = (int(round(v)) for v in box_xyxy)
        x1 = max(0, min(orig_w - 1, x1))
        x2 = max(1, min(orig_w, x2))
        y1 = max(0, min(orig_h - 1, y1))
        y2 = max(1, min(orig_h, y2))
        mask = np.zeros((orig_h, orig_w), dtype=np.float32)
        mask[y1:y2, x1:x2] = 1.0
        kernel = max(15, ((x2 - x1 + y2 - y1) // 16) | 1)  # odd, scales with box
        mask = cv2.GaussianBlur(mask, (kernel, kernel), 0)
        heatmap = heatmap * (0.25 + 0.75 * mask)

    # Re-normalize after masking so colors stay vibrant
    hmin, hmax = float(heatmap.min()), float(heatmap.max())
    if hmax > hmin:
        heatmap = (heatmap - hmin) / (hmax - hmin)

    heatmap_uint8 = (heatmap * 255).clip(0, 255).astype(np.uint8)
    heatmap_color = cv2.applyColorMap(heatmap_uint8, cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(image_bgr, 1 - alpha, heatmap_color, alpha, 0)

    # Draw the original box outline on top so it stays visible
    if box_xyxy is not None:
        x1, y1, x2, y2 = (int(round(v)) for v in box_xyxy)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 255, 255), 2)

    ok, buf = cv2.imencode(".png", overlay, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not ok:
        raise RuntimeError("failed to encode PNG")
    return buf.tobytes()
