"""Tiny dependency-free PDF writer for documents the assistant creates.

Understands a small Markdown subset: '# ', '## ', '### ' headings, '- ' / '* ' / '1. ' list
items, '---' rules, and blank-line separated paragraphs. **bold** markers are stripped.
"""
from __future__ import annotations

import re
import time

PAGE_W, PAGE_H = 595.0, 842.0  # A4 in points
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 64.0, 72.0, 64.0

# Helvetica / Helvetica-Bold advance widths (1/1000 em) for ASCII 32..126
_HELV = [278,278,355,556,556,889,667,191,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,278,278,584,584,584,556,1015,667,667,722,722,667,611,778,722,278,500,667,556,833,722,778,667,778,722,667,611,722,667,944,667,667,611,278,278,278,469,556,333,556,556,500,556,556,278,556,556,222,222,500,222,833,556,556,556,556,333,500,278,556,500,722,500,500,500,334,260,334,584]
_HELVB = [278,333,474,556,556,889,722,238,333,333,389,584,278,333,278,278,556,556,556,556,556,556,556,556,556,556,333,333,584,584,584,611,975,722,722,722,722,667,611,778,722,278,556,722,611,833,722,778,667,778,722,667,611,722,667,944,667,667,611,333,278,333,584,556,333,556,611,556,611,556,333,611,611,278,278,556,278,889,611,611,611,611,389,556,333,611,556,778,556,556,500,389,280,389,584]


def _w(text: str, size: float, bold: bool) -> float:
    table = _HELVB if bold else _HELV
    return sum(table[ord(c) - 32] if 32 <= ord(c) <= 126 else 556 for c in text) * size / 1000


def _wrap(text: str, size: float, bold: bool, width: float) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        cand = f"{cur} {word}".strip()
        if _w(cand, size, bold) <= width or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


_SUBS = str.maketrans({"→": "->", "←": "<-", "⇒": "=>", "≥": ">=", "≤": "<=", "≠": "!=", "×": "x", "✓": "v", "✗": "x",
                       "−": "-", "\u00a0": " ", "\u2009": " ", "\u202f": " "})


def _esc(s: str) -> bytes:
    b = s.translate(_SUBS).encode("cp1252", "replace")
    return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _blocks(md: str):
    para: list[str] = []
    table: list[list[str]] = []

    def flush_table():
        if table:
            yield ("table", [r[:] for r in table])
            table.clear()

    def flush():
        yield from flush_table()
        if para:
            yield ("p", " ".join(para))
            para.clear()

    for raw in md.replace("\r\n", "\n").split("\n"):
        line = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), raw.rstrip())
        line = re.sub(r"`([^`]*)`", r"\1", line)
        s = line.strip()
        if s.startswith("|") and s.count("|") >= 2:
            if para:
                yield ("p", " ".join(para)); para.clear()
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                table.append(cells)
            continue
        yield from flush_table()
        if not s:
            yield from flush()
            continue
        if m := re.match(r"^(#{1,3})\s+(.*)", s):
            yield from flush()
            yield (f"h{len(m.group(1))}", m.group(2))
        elif re.match(r"^(-{3,}|\*{3,})$", s):
            yield from flush()
            yield ("hr", "")
        elif m := re.match(r"^([-*•]|\d+[.)])\s+(.*)", s):
            yield from flush()
            yield ("li", (m.group(1) if m.group(1)[0].isdigit() else "•", m.group(2)))
        else:
            para.append(s)
    yield from flush()


def make_pdf(title: str, markdown: str) -> bytes:
    width = PAGE_W - 2 * MARGIN_X
    pages: list[list[bytes]] = [[]]
    y = PAGE_H - MARGIN_TOP

    def need(h: float):
        nonlocal y
        if y - h < MARGIN_BOTTOM:
            pages.append([])
            y = PAGE_H - MARGIN_TOP

    def text_line(x: float, s: str, size: float, bold: bool, gray: float = 0.1):
        font = "F2" if bold else "F1"
        pages[-1].append(b"BT /%s %.1f Tf %.3f g %.2f %.2f Td (%s) Tj ET" % (font.encode(), size, gray, x, y, _esc(s)))

    # title block
    for ln in _wrap(title, 22, True, width):
        need(28); y -= 24; text_line(MARGIN_X, ln, 22, True)
    y -= 8
    stamp = "Created by the Shelfie assistant · " + time.strftime("%d %b %Y")
    need(14); y -= 10; text_line(MARGIN_X, stamp, 8.5, False, 0.45)
    y -= 10
    pages[-1].append(b"0.85 0.28 0.12 RG 1.2 w %.2f %.2f m %.2f %.2f l S" % (MARGIN_X, y, MARGIN_X + 60, y))
    y -= 18

    first = True
    for kind, body in _blocks(markdown):
        if first and kind == "h1" and body.strip().lower() == title.strip().lower():
            first = False
            continue  # the title block already shows it
        first = False
        if kind in ("h1", "h2", "h3"):
            size = {"h1": 16, "h2": 13.5, "h3": 11.5}[kind]
            y -= 8
            for ln in _wrap(body, size, True, width):
                need(size + 6); y -= size + 3; text_line(MARGIN_X, ln, size, True)
            y -= 4
        elif kind == "table":
            rows = body
            ncol = max(len(r) for r in rows)
            rows = [r + [""] * (ncol - len(r)) for r in rows]
            natural = [max(_w(r[c], 10, True) for r in rows) + 14 for c in range(ncol)]
            scale = min(1.0, width / sum(natural))
            cols = [n * scale for n in natural]
            y -= 4
            for ri, r in enumerate(rows):
                bold = ri == 0 or (ri == len(rows) - 1 and any(k in r[0].lower() for k in ("total", "sum")))
                wrapped = [_wrap(cell, 10, bold, cols[c] - 10) for c, cell in enumerate(r)]
                h = max(len(w) for w in wrapped) * 13 + 6
                need(h + 2)
                if ri == 1 or (bold and ri):
                    pages[-1].append(b"0.75 G 0.6 w %.2f %.2f m %.2f %.2f l S" % (MARGIN_X, y, MARGIN_X + sum(cols), y))
                x = MARGIN_X
                top = y
                for c, lines in enumerate(wrapped):
                    y = top
                    for ln in lines:
                        y -= 13; text_line(x, ln, 10, bold, 0.1 if bold or c == 0 else 0.25)
                    x += cols[c]
                y = top - h
            pages[-1].append(b"0.75 G 0.6 w %.2f %.2f m %.2f %.2f l S" % (MARGIN_X, y + 3, MARGIN_X + sum(cols), y + 3))
            y -= 8
        elif kind == "hr":
            need(16); y -= 8
            pages[-1].append(b"0.8 g 0.5 w 0.8 G %.2f %.2f m %.2f %.2f l S" % (MARGIN_X, y, PAGE_W - MARGIN_X, y))
            y -= 8
        elif kind == "li":
            bullet, txt = body
            indent = 16
            for i, ln in enumerate(_wrap(txt, 10.5, False, width - indent)):
                need(15); y -= 14.5
                if i == 0:
                    text_line(MARGIN_X + 2, bullet, 10.5, False)
                text_line(MARGIN_X + indent, ln, 10.5, False)
            y -= 2
        else:
            for ln in _wrap(body, 10.5, False, width):
                need(15); y -= 14.5; text_line(MARGIN_X, ln, 10.5, False)
            y -= 7

    # assemble
    objs: list[bytes] = []
    n_pages = len(pages)
    page_ids = [5 + i * 2 for i in range(n_pages)]
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % p for p in page_ids), n_pages))
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, ops in enumerate(pages):
        footer = b"BT /F1 8 Tf 0.55 g %.2f 36 Td (%d / %d) Tj ET" % (PAGE_W - MARGIN_X - 20, i + 1, n_pages)
        stream = b"\n".join(ops + [footer])
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>"
                    % (PAGE_W, PAGE_H, page_ids[i] + 1))
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    info_id = len(objs) + 1
    objs.append(b"<< /Title (%s) /Producer (Shelfie) >>" % _esc(title))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, info_id, xref)
    return bytes(out)
