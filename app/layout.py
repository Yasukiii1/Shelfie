
Vision models are good at reading and bad at geometry, so geometry is measured, not guessed:
  • text lines: OCR boxes, then baseline / letter height / exact left-right ink extent measured from pixels;
    each line is horizontally scaled so it spans exactly the width it has in the photo
  • rules and boxes: long thin ink runs found with morphology, drawn at their real position and thickness
  • logos, pictures, graphs: traced from their outlines into colour-layered vector paths (a one-to-one drawing,
    never the photo's pixels); text inside them is kept as invisible, searchable text
  • the vision model only corrects wording, marks bold / superscripts / fonts, and adds text OCR missed
"""
from __future__ import annotations

import base64
import difflib
import functools
import io
import json
import re
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFont, ImageOps

WORK_W = 1600  # analysis resolution (px); SVG uses the same coordinates
FONTS = {
    ("sans", False): "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
    ("sans", True): "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
    ("serif", False): "/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf",
    ("serif", True): "/usr/share/fonts/opentype/urw-base35/NimbusRoman-Bold.otf",
    ("mono", False): "/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf",
    ("mono", True): "/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Bold.otf",
}
FAMILY = {"sans": "Nimbus Sans, Arial, Helvetica, sans-serif", "serif": "Nimbus Roman, Times New Roman, serif",
          "mono": "Nimbus Mono PS, Courier New, monospace", "hand": "Comic Neue, Comic Sans MS, cursive"}
CAP = {"sans": 0.72, "serif": 0.66, "mono": 0.6, "hand": 0.7}  # cap height / font size
SVG_NS = "http://www.w3.org/2000/svg"


# ---------------------------------------------------------------- helpers
@functools.lru_cache(maxsize=64)
def _font(family: str, bold: bool, size: int):
    path = FONTS.get((family if family in ("sans", "serif", "mono") else "sans", bold))
    try:
        return ImageFont.truetype(path, max(4, size))
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(4, size))


def _ocr():
    from .enhance import _ocr as o
    return o(False)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, c))) for c in rgb)


def _parse_markup(text: str) -> list[tuple[str, str, bool]]:
    """'ms^{-1} **Colour**' → [(chunk, 'normal'|'sup'|'sub', bold)]"""
    out, bold = [], False
    for tok in re.split(r"(\*\*|\^\{[^}]*\}|_\{[^}]*\}|\^-?\d+)", text):
        if not tok:
            continue
        if tok == "**":
            bold = not bold
        elif tok.startswith("^{"):
            out.append((tok[2:-1], "sup", bold))
        elif tok.startswith("^"):
            out.append((tok[1:], "sup", bold))
        elif tok.startswith("_{"):
            out.append((tok[2:-1], "sub", bold))
        else:
            out.append((tok, "normal", bold))
    return out


# ---------------------------------------------------------------- image prep
def load(path: Path) -> np.ndarray:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    w, h = im.size
    im = im.resize((WORK_W, round(h * WORK_W / w)), Image.LANCZOS if w < WORK_W else Image.BOX)
    return np.array(im)


def flatten(rgb: np.ndarray) -> np.ndarray:
    """Grey page with shadows / uneven light removed (paper → ~255)."""
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    k = (min(g.shape) // 16) | 1
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    bg = cv2.GaussianBlur(bg, (0, 0), k / 4)
    return np.clip(g / np.maximum(bg, 1) * 255, 0, 255).astype(np.uint8)


def deskew(rgb: np.ndarray, boxes) -> tuple[np.ndarray, float]:
    angles, weights = [], []
    for b in boxes:
        (x0, y0), (x1, y1) = b[0], b[1]
        ln = np.hypot(x1 - x0, y1 - y0)
        if ln > 80:
            angles.append(np.degrees(np.arctan2(y1 - y0, x1 - x0))); weights.append(ln)
    if not angles:
        return rgb, 0.0
    a = float(np.average(angles, weights=weights))
    if abs(a) < 0.15 or abs(a) > 10:
        return rgb, 0.0
    h, w = rgb.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
    return cv2.warpAffine(rgb, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE), a


# ---------------------------------------------------------------- analysis
def ocr_lines(rgb: np.ndarray) -> list[dict]:
    res = _ocr()(rgb)
    lines = []
    if res is None or getattr(res, "boxes", None) is None:
        return lines
    for box, txt, conf in zip(res.boxes, res.txts, res.scores):
        if not txt.strip() or conf < 0.45:
            continue
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        lines.append({"text": txt.strip(), "conf": float(conf), "x0": min(xs), "x1": max(xs), "y0": min(ys), "y1": max(ys), "quad": box})
    lines.sort(key=lambda l: (round(l["y0"] / 10), l["x0"]))
    for i, l in enumerate(lines):
        l["id"] = i
    return lines


def measure_line(ink: np.ndarray, rgb: np.ndarray, l: dict):
    """Exact ink extent, baseline, and letter height inside an OCR box."""
    H, W = ink.shape
    x0, x1 = max(0, int(l["x0"]) - 2), min(W, int(l["x1"]) + 2)
    y0, y1 = max(0, int(l["y0"]) - 1), min(H, int(l["y1"]) + 2)
    crop = ink[y0:y1, x0:x1]
    if crop.size == 0 or crop.sum() == 0:
        l.update(left=l["x0"], right=l["x1"], base=l["y1"] - (l["y1"] - l["y0"]) * .22, top=l["y0"], color=(25, 25, 25)); return
    rows = crop.sum(axis=1).astype(float); cols = crop.sum(axis=0)
    mx = rows.max()
    dense = np.where(rows >= mx * 0.35)[0]
    anyink = np.where(rows >= mx * 0.12)[0]  # ignores thin superscripts / stray marks above the line
    base = y0 + dense.max() + 1           # bottom of the x-height mass = baseline
    top = y0 + anyink.min()               # tallest letters (caps / ascenders)
    mid = np.where(rows >= mx * 0.5)[0]
    xh = float(base - (y0 + mid.min())) if len(mid) else float(base - top)
    letters = [c for c in l["text"] if c.isalpha()]
    lower = sum(c.islower() for c in letters) / max(1, len(letters))
    # body of lowercase letters (x-height) is dense and not disturbed by neighbours' descenders;
    # lines of digits / capitals use cap height instead
    l["size_est"] = xh / 0.52 if lower >= 0.5 else (base - top) / 0.72
    l["density"] = float(crop.sum()) / max(1.0, (crop.shape[1]) * max(1.0, xh))
    xs = np.where(cols > 0)[0]
    l.update(left=x0 + xs.min(), right=x0 + xs.max() + 1, base=float(base), top=float(top))
    pix = rgb[y0:y1, x0:x1][crop > 0]
    l["color"] = tuple(np.percentile(pix, 25, axis=0)) if len(pix) else (25, 25, 25)
    l["darkbg"] = float(crop.mean()) > 0.5  # white text on a dark bar (logos, banners)


def find_rules(ink: np.ndarray, text_mask: np.ndarray, core_mask: np.ndarray | None = None) -> tuple[list, np.ndarray]:
    H, W = ink.shape
    rules, mask = [], np.zeros_like(ink)
    for horiz in (True, False):
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, W // 40), 1) if horiz else (1, max(16, H // 90)))
        bridge = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 1) if horiz else (1, 5))
        m = cv2.morphologyEx(cv2.morphologyEx(ink, cv2.MORPH_CLOSE, bridge), cv2.MORPH_OPEN, k)  # faint/broken rules
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            thick = h if horiz else w
            length = w if horiz else h
            if thick > 10 or (thick >= 5 and length < W * 0.25 and length / max(thick, 1) < 30):  # a chunky bar/shape: trace it
                continue
            edge = W * 0.015
            if (not horiz and (x < edge or x + w > W - edge)) or (horiz and (y < edge or y + h > H - edge)):
                continue  # the paper's edge / photo border
            if horiz and text_mask[y:y + h, x:x + w].mean() > 0.85 and w < W * 0.05:
                continue
            if not horiz and text_mask[y:y + h, x:x + w].mean() > 0.3:
                continue  # a letter stroke (l, I, 1), not a box edge
            if horiz and core_mask is not None and core_mask[y:y + h, x:x + w].mean() > 0.3:
                continue  # runs through the middle of letters: joined strokes, not a rule
            rules.append({"horiz": horiz, "x0": x, "y0": y, "x1": x + w, "y1": y + h, "t": max(1.2, float(area) / max(w if horiz else h, 1))})
            mask[lab == i] = 1
    return rules, mask


def find_graphics(ink, text_mask, rule_mask, lines) -> list[tuple[int, int, int, int]]:
    H, W = ink.shape
    rest = ink.copy()
    for l in lines:
        if l.get("darkbg"):
            l["in_graphic"] = True  # banner/logo text: trace it with its background
    tm = text_mask.copy()
    for l in lines:
        if l.get("in_graphic"):
            tm[int(l["y0"]):int(l["y1"]) + 1, int(l["x0"]):int(l["x1"]) + 1] = 0
    rest[tm > 0] = 0
    rest[cv2.dilate(rule_mask, np.ones((5, 5), np.uint8)) > 0] = 0
    rest = cv2.morphologyEx(rest, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(rest, 8)
    keep = np.zeros_like(rest)
    for i in range(1, n):
        if stats[i][4] >= W * H * 0.0004:
            keep[lab == i] = 1
    if keep.sum() == 0:
        return []
    grow = max(6, W // 120)
    clusters = cv2.dilate(keep, np.ones((grow, grow), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(clusters, 8)
    regions = []
    for i in range(1, n):
        x, y, w, h, _ = stats[i]
        if w * h < W * H * 0.001:
            continue
        regions.append([x, y, x + w, y + h])
    for l in lines:  # a dark banner on its own is a graphic too
        if l.get("darkbg") and not any(l["x0"] < r[2] and l["x1"] > r[0] and l["y0"] < r[3] and l["y1"] > r[1] for r in regions):
            regions.append([int(l["x0"]), int(l["y0"]), int(l["x1"]), int(l["y1"])])
    # pull in text that sits on / tightly around a graphic (logo words, graph labels)
    changed = True
    while changed:
        changed = False
        for r in regions:
            for l in lines:
                if l.get("in_graphic") and not l.get("darkbg"):
                    continue
                if l.get("darkbg"):
                    continue
                lh = l["y1"] - l["y0"]
                gap = lh * 0.6
                if l["x1"] > r[0] - gap and l["x0"] < r[2] + gap and l["y1"] > r[1] - gap and l["y0"] < r[3] + gap:
                    # only text that mostly sits over the graphic's own columns (logo words, graph labels)
                    lw = max(1.0, l["x1"] - l["x0"])
                    xov = (min(l["x1"], r[2]) - max(l["x0"], r[0])) / lw
                    if xov >= 0.6:
                        l["in_graphic"] = True
                        r[:] = [min(r[0], int(l["x0"])), min(r[1], int(l["y0"])), max(r[2], int(l["x1"])), max(r[3], int(l["y1"]))]
                        changed = True
    return [tuple(r) for r in regions]


def small_marks(ink, text_mask, rule_mask, graphics) -> list[str]:
    """Colons, dots, ticks, bullets and other small marks the OCR didn't read: trace them as-is."""
    H, W = ink.shape
    rest = ink.copy()
    rest[cv2.dilate(text_mask, np.ones((3, 3), np.uint8)) > 0] = 0
    rest[cv2.dilate(rule_mask, np.ones((5, 5), np.uint8)) > 0] = 0
    for x0, y0, x1, y1 in graphics:
        rest[y0:y1, x0:x1] = 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(rest, 8)
    parts = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < 6 or area > W * H * 0.0004 or max(w, h) > W * 0.05:
            continue
        if x < W * 0.015 or x + w > W * 0.985 or y < H * 0.01 or y + h > H * 0.99:
            continue  # photo border / paper edge
        m = (lab[y:y + h, x:x + w] == i).astype(np.uint8)
        for c in cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            c = cv2.approxPolyDP(c, 0.5, True).reshape(-1, 2)
            if len(c) >= 3:
                parts.append("M" + " L".join(f"{p[0] + x:.1f} {p[1] + y:.1f}" for p in c) + "Z")
    return [f'<path fill="#1e1e1e" d="{" ".join(parts)}"/>'] if parts else []


def trace_region(rgb, flat, box) -> list[str]:
    """Colour-layered vector trace of a region. Returns SVG <path> strings."""
    x0, y0, x1, y1 = box
    crop, fl = rgb[y0:y1, x0:x1], flat[y0:y1, x0:x1]
    inkm = (fl < 170).astype(np.uint8)
    if inkm.sum() < 20:
        return []
    px = crop[inkm > 0].astype(np.float32)
    k = 1 if px.std(axis=0).max() < 18 else min(4, max(2, len(px) // 4000 + 1))
    if k > 1:
        _, labels, centers = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS)
        labels = labels.ravel()
    else:
        labels, centers = np.zeros(len(px), np.int32), px.mean(axis=0, keepdims=True)
    full = np.full(inkm.shape, -1, np.int32)
    full[inkm > 0] = labels
    paths = []
    order = np.argsort([-(c.mean()) for c in centers])  # light layers first, dark on top
    for ci in order:
        m = (full == ci).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        if m.sum() < 8:
            continue
        cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        parts = []
        for c in cs:
            if cv2.contourArea(c) < 2.5:
                continue
            c = cv2.approxPolyDP(c, 0.7, True).reshape(-1, 2)
            if len(c) < 3:
                continue
            parts.append("M" + " L".join(f"{p[0] + x0:.1f} {p[1] + y0:.1f}" for p in c) + "Z")
        if parts:
            col = centers[ci]
            if col.mean() > 150 and np.ptp(col) < 30:
                continue  # light grey without colour: shadow or paper texture, not part of the drawing
            if col.mean() < 70:
                col = col * 0.6  # near-black ink prints as black, not photo-grey
            paths.append(f'<path fill="{_hex(col)}" fill-rule="evenodd" d="{" ".join(parts)}"/>')
    return paths


# ---------------------------------------------------------------- the AI pass
AI_PROMPT = """This is a photo of a printed page. A text reader found these lines (id, then box x,y,w,h in a {w}x{h} image, then what it read):
{lines}

Your job is ONLY to get the words exactly right and describe their style. For every id:
- "text": the exact printed text of that box. Fix misreadings. Mark bold or highlighted words with **…**, superscripts with ^{{…}} (e.g. ms^{{-1}}, m^{{2}}) and subscripts with _{{…}} (e.g. H_{{2}}O).
- "font": "sans", "serif", "mono" or "hand" (handwriting).
- "bold": true if the whole line is bold.
Then list printed text the reader MISSED (small symbols like ":" count) in "extra", each with its box x,y,w,h in the same coordinates.
Also give the page a short "title".
Reply with JSON only: {{"title": "…", "lines": [{{"id": 0, "text": "…", "font": "sans", "bold": false}}], "extra": [{{"text": "…", "x": 0, "y": 0, "w": 0, "h": 0, "font": "sans", "bold": false}}]}}"""


def ai_correct(llama_url: str, rgb: np.ndarray, lines: list[dict], on_tokens=None) -> dict:
    im = Image.fromarray(rgb); im.thumbnail((1536, 1536))
    k = im.width / rgb.shape[1]
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
    listing = "\n".join(f'{l["id"]}: ({int(l["x0"]*k)},{int(l["y0"]*k)},{int((l["x1"]-l["x0"])*k)},{int((l["y1"]-l["y0"])*k)}) "{l["text"]}"' for l in lines)
    body = {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": AI_PROMPT.format(w=im.width, h=im.height, lines=listing)}]}],
        "temperature": 0.1, "max_tokens": 6000, "stream": True, "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(llama_url + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    out, n = [], 0
    with urllib.request.urlopen(req, timeout=1200) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            try:
                d = json.loads(line[5:])["choices"][0]["delta"].get("content") or ""
            except Exception:
                continue
            out.append(d); n += 1
            if on_tokens and n % 25 == 0:
                on_tokens(n)
    s = "".join(out)
    try:
        data = json.loads(s[s.index("{"): s.rindex("}") + 1])
    except Exception:
        return {}
    for e in data.get("extra", []) or []:  # back to analysis coordinates
        for key in ("x", "y", "w", "h"):
            if isinstance(e.get(key), (int, float)):
                e[key] = e[key] / k
    return data


def merge_ai(lines: list[dict], ai: dict) -> list[dict]:
    by_id = {l.get("id"): l for l in ai.get("lines", []) if isinstance(l, dict)}
    for l in lines:
        a = by_id.get(l["id"])
        l["font"], l["bold"], l["markup"] = "sans", False, l["text"]
        if not a:
            continue
        plain = re.sub(r"\*\*|\^\{|_\{|\}", "", str(a.get("text", "")))
        sim = difflib.SequenceMatcher(None, plain.lower(), l["text"].lower()).ratio()
        if a.get("text") and (sim >= 0.45 or l["conf"] < 0.8):
            l["markup"] = str(a["text"])
        l["font"] = a.get("font") if a.get("font") in FAMILY else "sans"
        l["bold"] = bool(a.get("bold"))
        l["ai_style"] = True
    return lines


# ---------------------------------------------------------------- SVG assembly
def text_svg(l: dict, invisible: bool = False) -> str:
    fam, bold = l.get("font", "sans"), l.get("bold", False)
    parts = _parse_markup(l.get("markup", l["text"]))
    if bold:
        parts = [(t, kind, True) for t, kind, _ in parts]
    size = l.get("size") or l.get("size_est") or max(4.0, l["base"] - l["top"]) / CAP.get(fam, 0.72)
    if fam == "serif":
        size *= 0.52 / 0.45  # Times has a smaller x-height than Arial
    # measure natural width
    width = 0.0
    for t, kind, b in parts:
        sz = size * (0.62 if kind != "normal" else 1)
        width += _font(fam, b, int(round(sz * 4)) ).getlength(t) / 4
    target = max(4.0, l["right"] - l["left"])
    sx = target / width if width > 0 else 1.0
    if not 0.55 < sx < 1.8:  # measurement is off (merged boxes etc.): keep the letters sane
        size *= min(1.5, max(0.65, sx)); sx = min(1.25, max(0.8, sx))
    c = np.array(l.get("color", (25, 25, 25)), float)
    if c.max() - c.min() < 40:          # grey/black print: photos make it look lighter than it is
        c = np.full(3, min(40.0, c.mean() * 0.45))
    color = "#000000" if invisible else _hex(c)
    spans, carry = [], 0.0   # carry = baseline offset to undo on the next chunk (no zero-width helper glyphs)
    for t, kind, b in parts:
        attrs = ' font-weight="bold"' if b else ""
        if kind in ("sup", "sub"):
            off = -size * 0.38 if kind == "sup" else size * 0.2
            spans.append(f'<tspan{attrs} font-size="{size*0.62:.1f}" dy="{off + carry:.1f}">{_esc(t)}</tspan>')
            carry = -off
        else:
            dy = f' dy="{carry:.1f}"' if carry else ""
            spans.append(f'<tspan{attrs}{dy}>{_esc(t)}</tspan>')
            carry = 0.0
    vis = ' fill-opacity="0"' if invisible else ""
    return (f'<text transform="translate({l["left"]:.1f} {l["base"]:.1f}) scale({sx:.3f} 1)" x="0" y="0" xml:space="preserve" '
            f'font-family="{FAMILY.get(fam, FAMILY["sans"])}" font-size="{size:.1f}" fill="{color}"{vis}>{"".join(spans)}</text>')


def build_page(path: Path, llama_url: str | None, progress=None, keep_dir: Path | None = None) -> tuple[bytes, int, int, str, dict]:
    rgb = load(path)
    first = _ocr()(rgb)
    rgb, angle = deskew(rgb, list(first.boxes) if first is not None and getattr(first, "boxes", None) is not None else [])
    flat = flatten(rgb)
    ink = (flat < 165).astype(np.uint8)
    lines = ocr_lines(rgb)
    if len(lines) < 3:
        raise ValueError("too little readable text for measured layout")
    H, W = ink.shape
    text_mask = np.zeros_like(ink)
    for l in lines:
        text_mask[int(l["y0"]):int(l["y1"]) + 1, int(l["x0"]):int(l["x1"]) + 1] = 1
    # the "core" of each text line (between the tops of lowercase letters and the baseline): no rule can live there
    core = np.zeros_like(ink)
    for l in lines:
        hgt = l["y1"] - l["y0"]
        core[int(l["y0"] + hgt * 0.3):int(l["y1"] - hgt * 0.3) + 1, int(l["x0"]):int(l["x1"]) + 1] = 1
    rules, rule_mask = find_rules(ink, text_mask, core)
    text_ink = ink.copy()
    text_ink[cv2.dilate(rule_mask, np.ones((3, 3), np.uint8)) > 0] = 0  # box edges / underlines aren't letters
    for l in lines:
        measure_line(text_ink, rgb, l)
    graphics = find_graphics(ink, text_mask, rule_mask, lines)
    # safety check: did OCR find (almost) all the text? Otherwise the model-drawn method is the better bet.
    rest = ink.copy()
    rest[rule_mask > 0] = 0
    for x0, y0, x1, y1 in graphics:
        rest[y0:y1, x0:x1] = 0
    covered = np.zeros_like(ink)
    for l in lines:
        covered[max(0, int(l["y0"]) - 2):int(l["y1"]) + 3, max(0, int(l["x0"]) - 4):int(l["x1"]) + 5] = 1
    coverage = float((rest * covered).sum()) / max(1.0, float(rest.sum()))
    if coverage < 0.75:
        raise ValueError(f"OCR only covered {coverage:.0%} of the text; using the model-drawn method")
    title = ""
    if llama_url:
        if progress:
            progress("studying")
        ai = ai_correct(llama_url, rgb, lines, on_tokens=(lambda n: progress and progress("reading", n)))
        lines = merge_ai(lines, ai)
        title = str(ai.get("title", "")).strip()
        extra = [e for e in ai.get("extra", []) or [] if isinstance(e, dict) and e.get("text") and all(isinstance(e.get(k), (int, float)) for k in ("x", "y", "h"))
                 and re.search(r"[A-Za-z0-9]", str(e["text"]))]  # lone punctuation is already traced exactly
    else:
        lines = merge_ai(lines, {}); extra = []
    # extra text the OCR missed: measure it the same way where possible
    for e in extra:
        el = {"id": -1, "text": re.sub(r"\*\*|\^\{|_\{|\}", "", e["text"]), "markup": e["text"], "conf": 0.5, "font": e.get("font", "sans"), "bold": bool(e.get("bold")),
              "x0": e["x"], "y0": e["y"], "x1": e["x"] + max(e.get("w") or 0, e["h"] * 0.5 * len(e["text"])), "y1": e["y"] + e["h"]}
        if any(abs(el["y0"] - l["y0"]) < 6 and el["x0"] < l["x1"] and el["x1"] > l["x0"] for l in lines):
            continue  # overlaps text we already have
        measure_line(text_ink, rgb, el)
        lines.append(el)
    # one size per paragraph (lines that start near the same x, similar size, regular spacing)
    body = sorted([l for l in lines if l.get("size_est")], key=lambda l: l["y0"])
    groups: list[list] = []
    for l in body:
        g = next((g for g in reversed(groups[-4:]) if abs(l["x0"] - g[-1]["x0"]) < 60 and 0.75 < l["size_est"] / g[-1]["size_est"] < 1.33
                  and 0 < l["base"] - g[-1]["base"] < g[-1]["size_est"] * 1.8), None)
        (g.append(l) if g else groups.append([l]))
    for g in groups:
        med = float(np.median([l["size_est"] for l in g]))
        for l in g:
            l["size"] = med
    # bold fallback when the AI didn't say: noticeably thicker strokes than the page's normal text
    dens = [l["density"] for l in lines if l.get("density")]
    if dens:
        typical = float(np.median(dens))
        for l in lines:
            if not l.get("bold") and l.get("density", 0) > typical * 1.3 and not l.get("ai_style"):
                l["bold"] = True
    # ---- assemble
    out = [f'<svg xmlns="{SVG_NS}" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           f'<title>{_esc(title)}</title>', f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    for g in graphics:
        out.append(f'<g data-kind="graphic">{"".join(trace_region(rgb, flat, g))}</g>')
    out.extend(small_marks(ink, text_mask, rule_mask, graphics))
    for r in rules:
        col = "#1e1e1e"
        if r["horiz"]:
            y = (r["y0"] + r["y1"]) / 2
            out.append(f'<line x1="{r["x0"]}" y1="{y:.1f}" x2="{r["x1"]}" y2="{y:.1f}" stroke="{col}" stroke-width="{r["t"]:.1f}"/>')
        else:
            x = (r["x0"] + r["x1"]) / 2
            out.append(f'<line x1="{x:.1f}" y1="{r["y0"]}" x2="{x:.1f}" y2="{r["y1"]}" stroke="{col}" stroke-width="{r["t"]:.1f}"/>')
    for l in lines:
        out.append(text_svg(l, invisible=bool(l.get("in_graphic"))))
    out.append("</svg>")
    svg = "\n".join(out).encode()
    if keep_dir:
        (keep_dir / f"{path.stem}-layout.svg").write_bytes(svg)
    stats = {"engine": "measured", "coverage": round(coverage, 2), "texts": len(lines), "rules": len(rules), "graphics": len(graphics), "deskew": round(angle, 2)}
    return svg, W, H, title, stats
