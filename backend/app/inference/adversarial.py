"""
Adversarial perturbation for robustness testing.

Two attack modes:
  1. FGSM  — proper Fast Gradient Sign Method using model-gradient. This is
             what the published literature calls an adversarial attack. If
             the gradient path works, use this.
  2. noise — additive Gaussian noise scaled by epsilon. Not strictly
             adversarial, but a robust fallback that ALWAYS works, and
             demonstrates the same point visually (imperceptible pixel
             perturbation collapses detection counts).

For the hackathon demo we expose both via the `method` parameter. The pitch
line: "FGSM is the formal adversarial attack; noise is an environmental
robustness proxy. Both are supported; both fail the baseline model; both
motivate the v2 roadmap item on adversarial training."
"""

from __future__ import annotations

import numpy as np


def perturb_gaussian(image_bgr: np.ndarray, epsilon: float) -> np.ndarray:
    """Add Gaussian noise with σ = epsilon × 255 to the image.
    epsilon is in normalized units (0..1). Typical visible threshold ≈ 0.03."""
    if epsilon <= 0:
        return image_bgr.copy()
    sigma = float(epsilon) * 255.0
    noise = np.random.normal(0.0, sigma, image_bgr.shape).astype(np.float32)
    perturbed = np.clip(image_bgr.astype(np.float32) + noise, 0.0, 255.0)
    return perturbed.astype(np.uint8)


def perturb_fgsm(yolo_model, image_bgr: np.ndarray, epsilon: float) -> np.ndarray:
    """Fast Gradient Sign Method attack against the YOLO model.

    Preprocesses to 640² RGB [0,1], enables input gradient, computes loss as
    the negative mean of max-class-probability across predictions (so higher
    loss = LOWER confidence), then perturbs x along sign(∂loss/∂x) by ε.
    Returns a perturbed BGR image at the ORIGINAL resolution.
    """
    if epsilon <= 0:
        return image_bgr.copy()

    import cv2
    import torch

    inner = yolo_model.model
    inner.eval()
    device = next(inner.parameters()).device

    h, w = image_bgr.shape[:2]
    imgsz = 640
    r = min(imgsz / h, imgsz / w)
    new_w, new_h = max(1, int(round(w * r))), max(1, int(round(h * r)))
    pad_w = (imgsz - new_w) // 2
    pad_h = (imgsz - new_h) // 2

    resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    padded = np.full((imgsz, imgsz, 3), 114, dtype=np.uint8)
    padded[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = resized
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0

    x = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).contiguous().to(device)
    x.requires_grad_(True)

    # Forward pass (inner is the raw nn.Module; outputs vary in shape by
    # Ultralytics version, so try multiple structures)
    out = inner(x)
    if isinstance(out, (tuple, list)):
        pred = out[0]
    else:
        pred = out

    # YOLOv11 Detect head (inference mode) outputs [B, 4+nc, num_anchors]
    # where nc=8 for us. Class logits are at [4:4+nc].
    # After sigmoid, class_scores[b, c, i] is P(class c | anchor i).
    # "Maximum confidence across all anchors" is a strong proxy objective.
    if pred.dim() == 3 and pred.shape[1] >= 5:
        class_scores = pred[:, 4:, :].sigmoid()           # [B, nc, N]
        max_per_anchor = class_scores.max(dim=1).values   # [B, N]
        # Loss = mean of top-K most confident predictions. FGSM ascends in
        # sign(grad) direction → here we want to REDUCE confidence so we
        # subtract the gradient.
        K = min(32, max_per_anchor.shape[1])
        topk = torch.topk(max_per_anchor, K, dim=1).values
        loss = topk.mean()
    else:
        loss = pred.float().mean()

    inner.zero_grad()
    loss.backward()
    grad = x.grad.detach()
    sign_grad = grad.sign()

    # Perturb: SUBTRACT ε * sign(grad) to reduce class confidence
    x_adv = (x.detach() - float(epsilon) * sign_grad).clamp(0.0, 1.0)

    # Back to BGR, un-pad, un-scale to original size
    adv_rgb = (x_adv[0].cpu().numpy().transpose(1, 2, 0) * 255.0).astype(np.uint8)
    adv_bgr_padded = cv2.cvtColor(adv_rgb, cv2.COLOR_RGB2BGR)
    adv_cropped = adv_bgr_padded[pad_h:pad_h + new_h, pad_w:pad_w + new_w]
    adv_final = cv2.resize(adv_cropped, (w, h), interpolation=cv2.INTER_LINEAR)
    return adv_final


def perturb(
    yolo_model,
    image_bgr: np.ndarray,
    epsilon: float,
    method: str = "fgsm",
) -> tuple[np.ndarray, str]:
    """Dispatch to the requested attack. Returns (perturbed_image, method_actually_used).
    If FGSM throws for any reason (model-structure changes, device issues),
    falls back to Gaussian noise so the demo always completes."""
    if method == "noise" or epsilon <= 0:
        return perturb_gaussian(image_bgr, epsilon), "noise"
    try:
        return perturb_fgsm(yolo_model, image_bgr, epsilon), "fgsm"
    except Exception:
        # Silent fallback — caller can inspect returned method
        return perturb_gaussian(image_bgr, epsilon), "noise-fallback"
