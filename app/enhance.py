
1. Clean the photo: flatten shadows/uneven light, boost local contrast (CLAHE) on lightness only so
   colours and highlighter survive, and upscale small pages.
2. Deblur: try a few strengths (none, unsharp, Richardson–Lucy deconvolution at several blur sizes) and
   keep the version a dedicated OCR engine (RapidOCR) reads most confidently. Picking by OCR score avoids
   guessing the blur and avoids over-sharpening, which the literature warns erases thin strokes.
3. OCR hints: the OCR lines of the winning version, with positions mapped into the model's coordinate
   space, go into the prompt as a cross-check. The prompt tells the model to trust the image where it's
   clear, because hints on bad images can push a model into guessing.
"""
from __future__ import annotations

import functools

import cv2
import numpy as np
from PIL import Image

TARGET_LONG_SIDE = 1536


@functools.lru_cache(maxsize=2)
def _ocr(sensitive: bool = False):
    from rapidocr import RapidOCR
    if sensitive:  # finds faint/blurry text lines the default detector skips
        return RapidOCR(params={"Det.thresh": 0.15, "Det.box_thresh": 0.3, "Det.unclip_ratio": 1.8})
    return RapidOCR()


def _flatten_and_contrast(rgb: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    L, A, B = cv2.split(lab)
    h, w = L.shape
    k = max(31, (min(h, w) // 18) | 1)
    # background light = text removed by a big closing, then smoothed
    bg = cv2.morphologyEx(L, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 3)
    Lf = np.clip(L.astype(np.float32) / np.maximum(bg.astype(np.float32), 1) * 245, 0, 255).astype(np.uint8)
    Lc = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(Lf)
    return cv2.cvtColor(cv2.merge([Lc, A, B]), cv2.COLOR_LAB2RGB)


def _unsharp(rgb: np.ndarray, sigma: float = 1.2, amount: float = 0.8) -> np.ndarray:
    blur = cv2.GaussianBlur(rgb, (0, 0), sigma)
    return cv2.addWeighted(rgb, 1 + amount, blur, -amount, 0)


def _richardson_lucy(rgb: np.ndarray, sigma: float, iters: int = 12) -> np.ndarray:
    """Deconvolve a Gaussian blur on the lightness channel (colour channels left alone)."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    L = lab[..., 0].astype(np.float32) / 255 + 1e-3
    est = L.copy()
    ks = int(sigma * 6) | 1
    for _ in range(iters):
        conv = cv2.GaussianBlur(est, (ks, ks), sigma)
        rel = L / np.maximum(conv, 1e-3)
        est *= cv2.GaussianBlur(rel, (ks, ks), sigma)
        est = np.clip(est, 0, 1.2)
    lab[..., 0] = np.clip(est * 255, 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _score(result) -> float:
    """Characters read with high confidence; low-confidence guesses don't count."""
    if not result or not getattr(result, "txts", None):
        return 0.0
    return float(sum(len(t) * s for t, s in zip(result.txts, result.scores) if s > 0.85))


def blur_level(rgb: np.ndarray) -> float:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def enhance(img: Image.Image) -> tuple[Image.Image, dict]:
    rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    scale = TARGET_LONG_SIDE / max(h, w)
    if scale > 1.05:
        rgb = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_CUBIC)
    elif scale < 0.95:
        rgb = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    base = _flatten_and_contrast(rgb)
    candidates = {
        "original": rgb,
        "clean": base,
        "unsharp": _unsharp(base),
        "deblur-s1.5": _richardson_lucy(base, 1.5),
        "deblur-s2.5": _richardson_lucy(base, 2.5),
        "deblur-s4": _richardson_lucy(base, 4.0, iters=15),
    }
    best, best_score, best_res, scores = "original", -1.0, None, {}
    for sensitive in (False, True):
        ocr = _ocr(sensitive)
        for name, cand in candidates.items():
            res = ocr(cand)
            key = name + ("+sensitive" if sensitive else "")
            scores[key] = round(_score(res))
            if scores[key] > best_score:
                best, best_score, best_res = name, scores[key], res
        if best_score > 400:  # plenty of confident text already; the sensitive pass only matters on bad photos
            break
    out = Image.fromarray(candidates[best])
    info = {"variant": best, "scores": scores, "sharpness_before": round(blur_level(rgb)),
            "lines": _lines(best_res, out.width)}
    return out, info


def _lines(res, width: int) -> list[dict]:
    if not res or not getattr(res, "txts", None):
        return []
    out = []
    for box, txt, conf in zip(res.boxes, res.txts, res.scores):
        if conf < 0.6 or not txt.strip():
            continue
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        out.append({"text": txt.strip(), "x": min(xs), "y": max(ys), "h": max(ys) - min(ys), "conf": float(conf), "w_img": width})
    out.sort(key=lambda l: (round(l["y"] / 12), l["x"]))
    return out


def hints_for_prompt(lines: list[dict], view_w: int) -> str:
    if not lines:
        return ""
    k = view_w / lines[0]["w_img"]
    rows = [f'y={round(l["y"] * k)} x={round(l["x"] * k)} size≈{round(l["h"] * k * 0.8)}: {l["text"]}' for l in lines]
    return ("\n\nOCR HINTS: a text reader read an enhanced copy of this page. Each line gives the baseline y, left x and "
            "approximate font-size in YOUR coordinate system, then the text. Use these for exact spelling, numbers and "
            "positions, especially where the photo is blurry. They can miss superscripts (\"ms-1\" is ms⁻¹, write the -1 as "
            "a superscript) and can contain mistakes: where the image clearly shows something different, trust the image. "
            "Never invent text that is in neither.\n" + "\n".join(rows))


def readability(img: Image.Image) -> dict:
    """How readable is the text in this photo? Edge strength measured only where there is ink, at a fixed
    width. Calibrated on a real worksheet photo blurred step by step (see the Text Lens benchmark):
    >= 1.6 reads almost perfectly, 1.2–1.6 gets words but loses numbers, < 1.2 is mostly guesswork."""
    g = np.array(img.convert("L")).astype(np.float32)
    g = cv2.resize(g, (1000, max(1, round(1000 * g.shape[0] / g.shape[1]))), interpolation=cv2.INTER_AREA)
    lap = np.abs(cv2.Laplacian(g, cv2.CV_32F))
    ink = cv2.dilate((g < 170).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    score = float(np.percentile(lap[ink], 90)) if ink.any() else 0.0
    level = "good" if score >= 1.6 else "blurry" if score >= 1.2 else "unreadable"
    return {"sharpness": round(score, 2), "level": level}
