
The photo is NEVER embedded. The model redraws each page as SVG: every piece of text becomes a real
<text> element at its position (highlighted words in bold), lines/boxes/blanks become vector lines and
rectangles, and pictures/graphs are sketched with vector shapes. A sanitizer then removes anything that
could smuggle the original pixels back in (<image>, data: URIs, external references), and cairo turns
the SVG into a PDF page with selectable text.
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageOps

SVG_NS = "http://www.w3.org/2000/svg"
VIEW_W = 1000
ALLOWED = {"svg", "g", "text", "tspan", "line", "rect", "circle", "ellipse", "path", "polyline", "polygon",
           "defs", "marker", "title", "clipPath", "linearGradient", "stop", "pattern"}

PROMPT = """You are reconstructing a photographed or scanned page (a child's school worksheet) as a clean vector document.
Output ONE complete SVG and nothing else. Use exactly: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
The SVG coordinate system matches the photo: x from 0 (left) to {w} (right), y from 0 (top) to {h} (bottom).

Hard rules:
1. NEVER use <image>, <foreignObject>, data: URIs or links. Everything must be drawn.
2. Start with <title>a short title for this page</title>, then <rect width="{w}" height="{h}" fill="white"/>.
3. TEXT: copy every piece of printed text exactly (spelling, numbers, punctuation, line breaks) as <text> elements placed where the text is on the page. One <text> per line; x,y = left edge and baseline. Choose font-size to match the height of the letters in the photo. Use font-family="DejaVu Sans" for normal print, "DejaVu Serif" for serif headings, "Comic Neue, cursive" for handwriting.
4. Words that are highlighted, bold, or emphasised in the photo must use font-weight="bold" (use <tspan font-weight="bold"> inside a line). Highlighter marks may also get a light colored <rect> behind them.
   Superscripts and subscripts (units like ms⁻¹, m², H₂O) use <tspan baseline-shift="super" font-size="…smaller…"> or baseline-shift="sub".
5. Keep text colors (fill) close to the photo. Keep alignment: use text-anchor="middle" for centred titles.
6. STRUCTURE: draw answer blanks, underlines, boxes, tables, borders, number lines and dividers with <line>/<rect>/<path> at the same positions and FULL lengths/sizes as in the photo (measure where each line starts and ends), stroke colors close to the photo.
7. PICTURES and GRAPHS: sketch them as a faithful one-to-one vector copy at the same place and size using <path>, <circle>, <ellipse>, <rect>, <polygon>, <polyline>, <line> with fills and strokes that match. Graphs keep their axes, tick marks, labels, bars/points/lines and values.
8. Do not add anything that is not on the page, and do not leave anything out. No comments, no explanations, no markdown fences.
9. Keep the SVG compact: no indentation, whole-number coordinates, and wrap elements that share a style in a <g> with that style instead of repeating attributes. Never repeat the same element twice."""


def _post(url: str, body: dict, timeout: float):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def prepare_image(path: Path, max_side: int = 1536, lens: bool = False) -> tuple[str, int, int, dict]:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    info: dict = {}
    if lens:
        from .enhance import enhance
        im, info = enhance(im)
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode(), im.width, im.height, info


def ask_model_for_svg(llama_url: str, b64: str, w: int, h: int, on_tokens=None, extra: str = "") -> str:
    body = {
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": PROMPT.format(w=w, h=h) + extra},
        ]}],
        "temperature": 0.15, "top_p": 0.9, "max_tokens": 18000, "stream": True, "repeat_penalty": 1.05,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    out, n = [], 0
    with _post(llama_url + "/v1/chat/completions", body, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content") or ""
            except Exception:
                continue
            out.append(delta)
            n += 1
            if on_tokens and n % 40 == 0:
                on_tokens(n)
    return "".join(out)


_FONTS: dict = {}


def _measure(text: str, size: float, bold: bool, serif: bool) -> float:
    from PIL import ImageFont
    key = (round(size, 1), bold, serif)
    if key not in _FONTS:
        name = "DejaVuSerif" if serif else "DejaVuSans"
        try:
            _FONTS[key] = ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}{'-Bold' if bold else ''}.ttf", max(1, round(size)))
        except OSError:
            _FONTS[key] = None
    f = _FONTS[key]
    return f.getlength(text) if f else len(text) * size * 0.58


def _num(v, default=0.0) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)) or default)
    except ValueError:
        return default


def reflow_lines(root) -> int:
    """The model places each piece of a line (e.g. normal words, then a bold word) at a guessed x.
    Measure the real width with the real font and push touching/overlapping pieces apart so the
    line reads naturally. Highlight boxes that belonged to a piece move with it."""
    T = f"{{{SVG_NS}}}"
    texts, rects = [], []
    for parent in root.iter():
        for el in list(parent):
            tag = _local(el.tag)
            if tag == "text" and el.get("text-anchor", "start") == "start" and el.get("x") and el.get("y"):
                texts.append(el)
            elif tag == "rect":
                rects.append(el)
    rows: dict[int, list] = {}
    for el in texts:
        rows.setdefault(round(_num(el.get("y")) / 4), []).append(el)
    moved = 0
    for row in rows.values():
        row.sort(key=lambda e: _num(e.get("x")))
        for a, b in zip(row, row[1:]):
            size = _num(a.get("font-size"), 16)
            serif = "serif" in (a.get("font-family") or "").lower() and "sans" not in (a.get("font-family") or "").lower()
            width = 0.0
            for chunk, el in [(a.text or "", a)] + [((t.text or "") + (t.tail or ""), t) for t in a.iter(T + "tspan")]:
                bold = (el.get("font-weight") or a.get("font-weight") or "") in ("bold", "700", "800", "900")
                width += _measure(chunk, size, bold, serif)
            ax, bx = _num(a.get("x")), _num(b.get("x"))
            a_end = ax + width
            joined = (a.text or "").endswith(" ") or (b.text or "").startswith(" ") or re.match(r"[.,;:!?)\]’'”%]", (b.text or "")) is not None
            want = a_end + (0 if joined else size * 0.32)
            # only fix pieces that collide or nearly touch; leave real columns alone
            if bx < want and bx > ax:
                dx = want - bx
                b.set("x", f"{want:.1f}")
                by = _num(b.get("y"))
                for r in rects:
                    rx, ry, rh = _num(r.get("x")), _num(r.get("y")), _num(r.get("height"))
                    if abs(rx - bx) < size * 0.6 and ry - 2 <= by <= ry + rh + size * 0.4:
                        r.set("x", f"{rx + dx:.1f}")
                moved += 1
    # nothing may run off the page. Shrink whole paragraphs (nearby lines of the same size) together,
    # so a long line doesn't end up smaller than its neighbours.
    page_w = _num(root.get("viewBox", "0 0 1000 1000").split()[2], 1000)

    def full_width(el, size):
        w = _measure(el.text or "", size, el.get("font-weight") in ("bold", "700"), False)
        for t in el.iter(f"{{{SVG_NS}}}tspan"):
            ts = _num(t.get("font-size"), size) if t.get("font-size") else size
            w += _measure(t.text or "", ts, (t.get("font-weight") or el.get("font-weight")) in ("bold", "700"), False)
            w += _measure(t.tail or "", size, el.get("font-weight") in ("bold", "700"), False)
        return w

    # paragraphs = consecutive lines that start near the same x with a similar size and line gap
    by_y = sorted(texts, key=lambda e: _num(e.get("y")))
    groups: list[list] = []
    for el in by_y:
        size, y, x = _num(el.get("font-size"), 16), _num(el.get("y")), _num(el.get("x"))
        g = None
        for cand in reversed(groups[-3:]):
            last = cand[-1]
            ls, ly, lx = _num(last.get("font-size"), 16), _num(last.get("y")), _num(last.get("x"))
            if 0.75 <= size / ls <= 1.34 and 0 < y - ly <= max(size, ls) * 1.9 and abs(x - lx) <= 60 and \
                    (last.get("font-weight") or "") == (el.get("font-weight") or ""):
                g = cand; break
        (g.append(el) if g else groups.append([el]))
    for g in groups:
        fitted = []
        for el in g:
            size = _num(el.get("font-size"), 16)
            w, limit = full_width(el, size), page_w * 0.985 - _num(el.get("x"))
            fitted.append(size * min(1.0, limit / w) if w > 0 and limit > 0 else size)
        target = max(6.0, min(fitted))
        for el in g:
            size = _num(el.get("font-size"), 16)
            if abs(size - target) < 0.05:
                continue
            k = target / size
            el.set("font-size", f"{target:.1f}")
            for t in el.iter(f"{{{SVG_NS}}}tspan"):
                if t.get("font-size"):
                    t.set("font-size", f"{_num(t.get('font-size')) * k:.1f}")
            moved += 1
    # a horizontal rule may never strike through text: move it just below (or above) the words
    lines = [e for e in root.iter(f"{{{SVG_NS}}}line") if abs(_num(e.get("y1")) - _num(e.get("y2"))) < 1.5]
    for ln in lines:
        y, x1, x2 = _num(ln.get("y1")), *sorted((_num(ln.get("x1")), _num(ln.get("x2"))))
        for el in texts:
            size, by, tx = _num(el.get("font-size"), 16), _num(el.get("y")), _num(el.get("x"))
            tw = full_width(el, size)
            top, bottom = by - size * 0.72, by - size * 0.05
            if top + 1 < y < bottom and x1 < tx + tw and x2 > tx:
                ny = by + size * 0.28 if y > (top + bottom) / 2 else by - size * 0.95
                ln.set("y1", f"{ny:.1f}"); ln.set("y2", f"{ny:.1f}")
                moved += 1
                break
    # superscripts/subscripts: cairo renders baseline-shift unreliably, so use explicit dy nudges
    for el in texts:
        size = _num(el.get("font-size"), 16)
        for t in list(el.iter(f"{{{SVG_NS}}}tspan")):
            shift = (t.attrib.pop("baseline-shift", "") or "").strip()
            if shift not in ("super", "sub"):
                continue
            d = size * (0.38 if shift == "super" else -0.22)
            t.set("dy", f"{-d:.1f}")
            back = ET.Element(f"{{{SVG_NS}}}tspan", {"dy": f"{d:.1f}"})
            back.text, t.tail = t.tail or "\u200b", None
            parent = next(p for p in el.iter() if t in list(p))
            parent.insert(list(parent).index(t) + 1, back)
    # highlight boxes should cover their (bold) word
    for el in texts:
        x, y, size = _num(el.get("x")), _num(el.get("y")), _num(el.get("font-size"), 16)
        for r in rects:
            rx, ry, rw, rh = (_num(r.get(k)) for k in ("x", "y", "width", "height"))
            fill = (r.get("fill") or "").lower()
            if fill in ("white", "#fff", "#ffffff", "none") or rh > size * 2.2:
                continue
            if abs(rx - x) < size * 0.6 and ry - 2 <= y <= ry + rh + size * 0.4:
                bold = el.get("font-weight") in ("bold", "700")
                w = _measure(el.text or "", size, bold, False)
                if w > rw:
                    r.set("width", f"{w + (x - rx) + 4:.1f}")
    return moved


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def sanitize_svg(raw: str, w: int, h: int) -> tuple[bytes, str, dict]:
    """Return (clean svg bytes, title, stats). Raises ValueError if unusable."""
    m = re.search(r"<svg\b.*?(</svg>|$)", raw, re.S | re.I)
    if not m:
        raise ValueError("The model didn't return a drawing.")
    s = m.group(0)
    if not m.group(1):  # truncated: close what we can
        s = re.sub(r"<[^>]*$", "", s)
        for tag in ("text", "g", "svg"):
            opens = len(re.findall(rf"<{tag}\b(?![^>]*/>)", s)) - len(re.findall(rf"</{tag}>", s))
            s += f"</{tag}>" * max(0, opens)
    s = re.sub(r"<!DOCTYPE[^>]*>|<\?xml[^>]*\?>", "", s)
    s = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", s)
    if "xmlns=" not in s[:200]:
        s = s.replace("<svg", f'<svg xmlns="{SVG_NS}"', 1)
    root = ET.fromstring(s)
    removed = 0

    def clean(el):
        nonlocal removed
        for child in list(el):
            if _local(child.tag) not in ALLOWED:
                el.remove(child); removed += 1; continue
            for k in list(child.attrib):
                v = child.attrib[k]
                if _local(k) == "href" or re.search(r"data:|https?:|javascript:", v, re.I) or k.lower().startswith("on"):
                    del child.attrib[k]
            clean(child)

    clean(root)
    root.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")  # keep spaces around bold words
    moved = reflow_lines(root)
    root.set("viewBox", f"0 0 {w} {h}")
    root.set("width", str(w)); root.set("height", str(h))
    title_el = root.find(f"{{{SVG_NS}}}title")
    title = (title_el.text or "").strip() if title_el is not None else ""
    texts = root.iter(f"{{{SVG_NS}}}text")
    n_text = sum(1 for _ in texts)
    shapes = sum(1 for e in root.iter() if _local(e.tag) in ("path", "circle", "ellipse", "rect", "polygon", "polyline", "line"))
    if n_text == 0:
        raise ValueError("No text was recognised on this page.")
    ET.register_namespace("", SVG_NS)
    return ET.tostring(root, encoding="utf-8"), title, {"texts": n_text, "shapes": shapes, "removed": removed, "reflowed": moved}


def svgs_to_pdf(pages: list[tuple[bytes, int, int]], title: str) -> bytes:
    """Render each SVG page with cairo (text stays real, selectable text) and join the pages."""
    import subprocess
    import tempfile
    import cairosvg

    with tempfile.TemporaryDirectory() as td:
        files = []
        for i, (svg, w, h) in enumerate(pages):
            out = f"{td}/p{i:03d}.pdf"
            cairosvg.svg2pdf(bytestring=svg, write_to=out, output_width=595, output_height=round(595 * h / w))
            files.append(out)
        if len(files) == 1:
            return Path(files[0]).read_bytes()
        subprocess.run(["pdfunite", *files, f"{td}/all.pdf"], check=True, capture_output=True)
        return Path(f"{td}/all.pdf").read_bytes()


def convert_images(paths: list[Path], llama_url: str, progress=None, keep_dir: Path | None = None, lens: bool = True) -> tuple[bytes, str, list[dict]]:
    """Returns (pdf bytes, suggested title, per-page stats)."""
    pages, stats, title = [], [], ""
    for i, p in enumerate(paths, 1):
        # 1) measured layout engine: geometry from the photo, wording from the model
        try:
            from .layout import build_page

            def lp(stage, n=0, i=i):
                if progress:
                    progress(f"Your model is checking the wording on page {i} of {len(paths)}…" if stage == "studying"
                             else f"Checking wording on page {i} of {len(paths)}", i, n)
            if progress:
                progress(f"Measuring the layout of page {i} of {len(paths)}…", i, 0)
            t0 = time.time()
            svg, vw, vh, t, st = build_page(p, llama_url, lp, keep_dir=keep_dir)
            from .enhance import readability
            st["seconds"] = round(time.time() - t0)
            st["readability"] = readability(ImageOps.exif_transpose(Image.open(p)))
            pages.append((svg, vw, vh)); stats.append(st)
            title = title or t
            continue
        except Exception as e:
            if keep_dir:
                (keep_dir / f"page{i:02d}-layout-fallback.txt").write_text(repr(e))
        # 2) fallback for photos too blurry for OCR: the model redraws the whole page
        if progress:
            progress(f"{'Sharpening text on' if lens else 'Reading'} page {i} of {len(paths)}…", i, 0)
        b64, w, h, lens_info = prepare_image(p, lens=lens)
        # model works in a 1000-wide coordinate space with the photo's aspect ratio
        vw, vh = VIEW_W, round(VIEW_W * h / w)
        hints = ""
        if lens:
            from .enhance import hints_for_prompt
            hints = hints_for_prompt(lens_info.get("lines", []), vw)
            if keep_dir:
                (keep_dir / f"page{i:02d}-lens.jpg").write_bytes(base64.b64decode(b64))
        if progress:
            progress(f"Your model is studying page {i} of {len(paths)} (picture analysis runs on the CPU, about a minute)…", i, 0)
        last_err = None
        for attempt in range(2):
            t0 = time.time()
            raw = ask_model_for_svg(llama_url, b64, vw, vh,
                                    on_tokens=(lambda n, i=i: progress and progress(f"Redrawing page {i} of {len(paths)}", i, n)),
                                    extra=hints + ("" if attempt == 0 else "\nYour previous answer was not valid SVG or had no text. Output only valid SVG this time."))
            if keep_dir:
                (keep_dir / f"page{i:02d}-try{attempt + 1}.svg.txt").write_text(raw)
            try:
                svg, t, st = sanitize_svg(raw, vw, vh)
                st["seconds"] = round(time.time() - t0)
                from .enhance import readability
                st["readability"] = readability(ImageOps.exif_transpose(Image.open(p)))
                if lens:
                    st["lens"] = {k: lens_info[k] for k in ("variant", "scores", "sharpness_before")} | {"ocr_lines": len(lens_info.get("lines", []))}
                pages.append((svg, vw, vh)); stats.append(st)
                title = title or t
                break
            except (ValueError, ET.ParseError) as e:
                last_err = e
        else:
            raise ValueError(f"Page {i}: {last_err}")
    if progress:
        progress("Building the PDF…", len(paths), 0)
    title = (title or f"Scanned worksheet {time.strftime('%d %b %Y')}").strip()[:120]
    return svgs_to_pdf(pages, title), title, stats
