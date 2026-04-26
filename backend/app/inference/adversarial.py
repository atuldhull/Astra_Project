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
    the mean of top-K most-confident class scores across anchors (we subtract
    the gradient to LOWER confidence), then perturbs x along -ε·sign(grad).
    Returns a perturbed BGR image at the ORIGINAL resolution.

    Newer Ultralytics versions wrap the Detect head's `_inference` postprocess
    in `torch.inference_mode()`, which marks output tensors as non-backwardable
    (`Inference tensors cannot be saved for backward`). To work around that we
    put the model in TRAIN mode before the forward pass — train-mode head
    returns the raw per-level [cls, box] tensors with no inference_mode taint
    — then concatenate class outputs across the 3 FPN levels and compute the
    same top-K confidence proxy on those.
    """
    if epsilon <= 0:
        return image_bgr.copy()

    import cv2
    import torch

    inner = yolo_model.model
    was_training = inner.training
    # Crucial: train() mode skips the inference_mode-wrapped decode path.
    # We're not actually back-propping through training-loss; we just need
    # the gradient w.r.t. the input image, and train-mode outputs are
    # exactly the raw class/box tensors we want.
    inner.train()
    device = next(inner.parameters()).device

    try:
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

        with torch.enable_grad():
            out = inner(x)

        # YOLOv11 train-mode Detect head returns ONE of:
        #   (a) dict {"boxes": [B,reg*4,N], "scores": [B,nc,N], "feats": [...]} (most current Ultralytics)
        #   (b) list of 3 tensors [B, reg_max*4 + nc, H, W] (one per FPN level, older versions)
        # Fall back to extracting class logits from each.
        all_cls: torch.Tensor | None = None

        if isinstance(out, dict):
            if "scores" in out and hasattr(out["scores"], "dim"):
                # Already [B, nc, total_anchors] — perfect, no work needed.
                all_cls = out["scores"]
            elif "cls" in out and hasattr(out["cls"], "dim"):
                all_cls = out["cls"]

        if all_cls is None:
            # Fallback: list-of-tensors per FPN level.
            head = getattr(inner, "model", None)
            nc, reg_max = 8, 16
            if head is not None and len(head) > 0:
                last = head[-1]
                nc = int(getattr(last, "nc", nc))
                reg_max = int(getattr(last, "reg_max", reg_max))
            cls_chunks = []
            seq = out if isinstance(out, (list, tuple)) else [out]
            for level in seq:
                if hasattr(level, "dim") and level.dim() == 4:
                    cls = level[:, reg_max * 4 :, :, :]
                    B, C, H, W = cls.shape
                    cls_chunks.append(cls.reshape(B, C, H * W))
            if not cls_chunks:
                raise RuntimeError(f"Could not find class logits in head output: {type(out).__name__}")
            all_cls = torch.cat(cls_chunks, dim=2)

        # Confidence proxy: max class probability per anchor, mean of top-K.
        all_cls_p = all_cls.sigmoid()
        max_per_anchor = all_cls_p.max(dim=1).values        # [B, total_anchors]
        K = min(32, max_per_anchor.shape[1])
        topk = torch.topk(max_per_anchor, K, dim=1).values
        loss = topk.mean()

        inner.zero_grad(set_to_none=True)
        loss.backward()
        grad = x.grad.detach()
        sign_grad = grad.sign()

        # SUBTRACT ε·sign(grad) to drive confidence DOWN.
        x_adv = (x.detach() - float(epsilon) * sign_grad).clamp(0.0, 1.0)
    finally:
        # Restore original mode so subsequent inference works normally.
        if not was_training:
            inner.eval()

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
    except Exception as exc:
        # Log so we can debug, but don't fail the request — the demo always
        # completes via the noise fallback even when FGSM's gradient path
        # breaks (e.g. Ultralytics output-shape changes, CUDA OOM).
        import logging
        logging.getLogger("astra.adversarial").warning(
            "FGSM failed, falling back to noise: %s", exc, exc_info=True,
        )
        return perturb_gaussian(image_bgr, epsilon), "noise-fallback"
