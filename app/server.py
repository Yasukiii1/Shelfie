"""Shelfie HTTP server: JSON API + the web UI used by both the desktop window and the iPhone."""
from __future__ import annotations

import asyncio
import io
import re
import time
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import segno
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import Agent, llama_status, llama_has_vision, LLAMA_CMD, LLAMA_URL
from . import convert as converter
from .library import INBOX, Library
from .pdfgen import make_pdf

HERE = Path(__file__).parent
STATIC = HERE / "static"
ROOT = Path(os.environ.get("SHELFIE_ROOT", Path.home() / "Shelfie")).expanduser()
PORT = int(os.environ.get("SHELFIE_PORT", "8642"))

lib = Library(ROOT)
ACCESS_KEY = lib.setting("access_key") or secrets.token_urlsafe(18)
lib.set_setting("access_key", ACCESS_KEY)

agent = Agent(ROOT, PORT)

app = FastAPI(title="Shelfie", docs_url=None, redoc_url=None)

LOCAL = {"127.0.0.1", "::1", "localhost"}
PUBLIC_PATHS = ("/fonts/", "/icons/", "/manifest.webmanifest", "/app.css")


def is_local(request: Request) -> bool:
    return (request.client.host if request.client else "") in LOCAL


@app.middleware("http")
async def revalidate(request: Request, call_next):
    """App code must update immediately on every device; big vendored files may cache."""
    resp = await call_next(request)
    p = request.url.path
    if p == "/" or p.endswith((".js", ".css", ".html")) and not p.startswith("/vendor/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.middleware("http")
async def guard(request: Request, call_next):
    """This computer is always trusted. Phones need the access key (from the QR code) once."""
    if is_local(request) or request.url.path.startswith(PUBLIC_PATHS):
        return await call_next(request)
    key = request.query_params.get("key")
    if key and secrets.compare_digest(key, ACCESS_KEY):
        resp = await call_next(request)
        resp.set_cookie("shelfie_key", ACCESS_KEY, max_age=60 * 60 * 24 * 365 * 5, httponly=True, samesite="lax")
        return resp
    cookie = request.cookies.get("shelfie_key", "")
    if cookie and secrets.compare_digest(cookie, ACCESS_KEY):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "not paired"}, status_code=401)
    return HTMLResponse((STATIC / "pair.html").read_text(), status_code=401)


# ---------------- pages ----------------
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest(request: Request):
    # The home-screen app gets its own cookie jar on iOS, so bake the key into its start URL.
    authed = is_local(request) or secrets.compare_digest(request.cookies.get("shelfie_key", "") or "-", ACCESS_KEY)
    start = f"/?key={ACCESS_KEY}" if authed else "/"
    body = {
        "name": "Shelfie", "short_name": "Shelfie", "start_url": start, "scope": "/",
        "display": "standalone", "background_color": "#F3EFE6", "theme_color": "#F3EFE6",
        "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}],
    }
    return Response(json.dumps(body), media_type="application/manifest+json", headers={"Cache-Control": "no-store"})


# ---------------- API ----------------
class DocPatch(BaseModel):
    title: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    favorite: bool | None = None


class CategoryIn(BaseModel):
    name: str
    color: str | None = None


class CategoryPatch(BaseModel):
    name: str | None = None
    color: str | None = None


def public(d: dict) -> dict:
    d = dict(d)
    d["tags"] = [t for t in d["tags"].split(",") if t]
    d["thumb"] = f"/api/docs/{d['id']}/thumb?v={int(d['processed'])}"
    d["processing"] = not d["processed"]
    return d


@app.get("/api/state")
def state(request: Request):
    return {"stats": lib.stats(), "categories": lib.categories(), "tags": lib.tags(), "local": is_local(request)}


@app.get("/api/version")
def version():
    s = lib.stats()
    return {"version": s["version"], "pending": s["pending"]}


@app.get("/api/docs")
def docs(category: str | None = None, tag: str | None = None, starred: bool = False,
         sort: str = "added", q: str | None = None):
    return [public(d) for d in lib.list_docs(category, tag, starred, sort, q)]


@app.get("/api/docs/{doc_id}")
def doc(doc_id: int):
    d = lib.doc(doc_id)
    if not d:
        raise HTTPException(404)
    return public(d)


@app.patch("/api/docs/{doc_id}")
def patch_doc(doc_id: int, p: DocPatch):
    try:
        return public(lib.update_doc(doc_id, p.title, p.category, p.tags, p.favorite))
    except KeyError:
        raise HTTPException(404)


@app.delete("/api/docs/{doc_id}")
def delete_doc(doc_id: int):
    lib.delete_doc(doc_id)
    return {"ok": True}


@app.get("/api/docs/{doc_id}/file")
def doc_file(doc_id: int, download: bool = False):
    d = lib.doc(doc_id)
    if not d:
        raise HTTPException(404)
    lib.mark_opened(doc_id)
    path = lib.abs(d["path"])
    disp = "attachment" if download else "inline"
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type=disp)


@app.get("/api/docs/{doc_id}/thumb")
def doc_thumb(doc_id: int):
    p = lib.thumbs / f"{doc_id}.jpg"
    if not p.exists():
        return Response(status_code=404)
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.post("/api/docs/{doc_id}/open-external")
def open_external(doc_id: int, request: Request, reveal: bool = False):
    if not is_local(request):
        raise HTTPException(403)
    d = lib.doc(doc_id)
    if not d:
        raise HTTPException(404)
    path = lib.abs(d["path"])
    if reveal:
        # select the file in the file manager when possible
        try:
            subprocess.Popen(["nautilus", "--select", str(path)], start_new_session=True)
        except FileNotFoundError:
            subprocess.Popen(["xdg-open", str(path.parent)], start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", str(path)], start_new_session=True)
    return {"ok": True}


def _meta_args(titles: str, tags: str, star: str):
    try:
        names = json.loads(titles) if titles else []
    except ValueError:
        names = []
    tag_list = [t for t in (x.strip() for x in tags.split(",")) if t]
    return names, tag_list, star in ("1", "true", "yes")


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), category: str = Form(INBOX),
                 titles: str = Form(""), tags: str = Form(""), star: str = Form("")):
    names, tag_list, starred = _meta_args(titles, tags, star)
    added = []
    for idx, f in enumerate(files):
        if not (f.filename or "").lower().endswith(".pdf") and f.content_type != "application/pdf":
            continue
        with tempfile.NamedTemporaryFile(delete=False, dir=lib.meta, suffix=".part") as tmp:
            while chunk := await f.read(1 << 20):
                tmp.write(chunk)
        with open(tmp.name, "rb") as fh:
            if fh.read(5) != b"%PDF-":
                os.unlink(tmp.name)
                continue
        name = (names[idx] if idx < len(names) and str(names[idx]).strip() else None)
        doc_id = lib.add_file((name + ".pdf") if name else (f.filename or "Untitled.pdf"), Path(tmp.name), category)
        if tag_list or starred:
            lib.update_doc(doc_id, tags=tag_list or None, favorite=True if starred else None)
        added.append(doc_id)
    return {"added": added}


@app.get("/api/docs/{doc_id}/text")
def doc_text(doc_id: int, start: int = 1, end: int = 10):
    """Plain text of a page range, for the assistant (and anything else that wants it)."""
    d = lib.doc(doc_id)
    if not d:
        raise HTTPException(404, f"No document with id {doc_id}")
    pages = d["pages"] or 1
    start = max(1, min(start, pages))
    end = max(start, min(end, pages, start + 29))
    out = subprocess.run(["pdftotext", "-f", str(start), "-l", str(end), "-layout", "-enc", "UTF-8", str(lib.abs(d["path"])), "-"],
                         capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
    chunks = out.split("\f")
    text = "\n".join(f"--- page {start + i} ---\n{c.strip()}" for i, c in enumerate(chunks) if c.strip() or i < end - start + 1)
    import re as _re
    text = _re.sub(r"[ \t]{3,}", "  ", text)
    limit = 24000
    return {"id": d["id"], "title": d["title"], "category": d["category"], "pages": pages, "start": start, "end": end,
            "text": text[:limit], "truncated": len(text) > limit}


class CreateIn(BaseModel):
    title: str
    content: str
    drawer: str = INBOX


@app.post("/api/agent/create")
def agent_create(c: CreateIn, request: Request):
    if not is_local(request):
        raise HTTPException(403)
    title = c.title.strip()[:150] or "Untitled"
    with tempfile.NamedTemporaryFile(delete=False, dir=lib.meta, suffix=".part") as tmp:
        tmp.write(make_pdf(title, c.content))
    doc_id = lib.add_file(title + ".pdf", Path(tmp.name), c.drawer or INBOX)
    lib.update_doc(doc_id, tags=["by-assistant"])
    return public(lib.doc(doc_id))


# ---------------- assistant ----------------
def ws_authorized(ws: WebSocket) -> bool:
    host = ws.client.host if ws.client else ""
    if host in LOCAL:
        return True
    cookie = ws.cookies.get("shelfie_key", "")
    return bool(cookie) and secrets.compare_digest(cookie, ACCESS_KEY)


@app.get("/api/agent/status")
def agent_status(request: Request):
    return {**agent.state(), "local": is_local(request), "command": LLAMA_CMD}


@app.get("/api/agent/chats")
def agent_chats():
    return {"chats": agent.list_chats(), "current": agent.chat_info()}


@app.delete("/api/agent/chats/{cid}")
def agent_delete_chat(cid: str):
    if not re.fullmatch(r"[\w-]+", cid):
        raise HTTPException(400)
    agent.delete_chat(cid)
    return {"ok": True}


# ---------------- image → PDF ----------------
CONVERT_DIR = lib.meta / "convert"
convert_lock = threading.Lock()
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".gif", ".tif", ".tiff")


@app.post("/api/convert")
async def convert_upload(files: list[UploadFile] = File(...), category: str = Form(INBOX), lens: str = Form("1"),
                         title: str = Form(""), tags: str = Form(""), star: str = Form(""), note: str = Form("")):
    if llama_status() != "online":
        raise HTTPException(409, "Start the model first (Librarian panel → Start model).")
    if not await asyncio.to_thread(llama_has_vision):
        raise HTTPException(409, "Your model is running without vision. Start llama-server with --mmproj.")
    job = time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    d = CONVERT_DIR / job
    d.mkdir(parents=True)
    paths = []
    for i, f in enumerate(files):
        ext = Path(f.filename or "").suffix.lower()
        if ext not in IMAGE_EXT and not (f.content_type or "").startswith("image/"):
            continue
        p = d / f"{i:02d}{ext or '.jpg'}"
        with open(p, "wb") as out:
            while chunk := await f.read(1 << 20):
                out.write(chunk)
        # small preview for the chat card
        try:
            from PIL import Image, ImageOps
            im = ImageOps.exif_transpose(Image.open(p)).convert("RGB"); im.thumbnail((320, 320))
            im.save(d / f"{i:02d}.thumb.jpg", "JPEG", quality=80)
        except Exception:
            pass
        paths.append(p)
    if not paths:
        raise HTTPException(400, "No images found.")
    n = len(paths)
    if note.strip():  # what the user typed alongside the photos: shown in the chat, not sent to the model
        agent.push_item({"kind": "user", "text": note.strip()[:2000], "t": time.time(), "title": note.strip()[:70]})
    agent.push_item({"kind": "convert", "job": job, "status": "running", "pages": n, "drawer": category,
                     "stage": "Waiting for the model…", "tokens": 0, "title": f"{n} photo{'s' if n > 1 else ''} → PDF",
                     "thumbs": [f"/api/convert/{job}/thumb/{i}" for i in range(n)]})
    meta = {"title": title.strip()[:150], "tags": [t for t in (x.strip() for x in tags.split(",")) if t], "star": star in ("1", "true")}
    threading.Thread(target=_run_convert, args=(job, paths, category, lens != "0", meta), daemon=True).start()
    return {"job": job}


def _run_convert(job: str, paths: list[Path], category: str, lens: bool = True, meta: dict | None = None):
    meta = meta or {}
    match = {"kind": "convert", "job": job}
    last = [0.0]

    def progress(stage, page, tokens):
        now = time.time()
        if now - last[0] > 0.6 or tokens == 0:
            last[0] = now
            agent.update_item(match, stage=stage, page=page, tokens=tokens)

    with convert_lock:
        try:
            pdf, title, stats = converter.convert_images(paths, LLAMA_URL, progress, keep_dir=paths[0].parent, lens=lens)
            title = meta.get("title") or title
            with tempfile.NamedTemporaryFile(delete=False, dir=lib.meta, suffix=".part") as tmp:
                tmp.write(pdf)
            doc_id = lib.add_file(title + ".pdf", Path(tmp.name), category)
            lib.update_doc(doc_id, tags=["from-image", *meta.get("tags", [])], favorite=True if meta.get("star") else None)
            bad = [i + 1 for i, st in enumerate(stats) if st.get("readability", {}).get("level") != "good"]
            worst = "unreadable" if any(st.get("readability", {}).get("level") == "unreadable" for st in stats) else "blurry"
            warning = "" if not bad else (
                f"Page {', '.join(map(str, bad))} {'is' if len(bad) == 1 else 'are'} "
                + ("too blurry to read reliably. Most of the text is likely wrong; please retake the photo."
                   if worst == "unreadable" else "blurry. Words are mostly right but check the numbers."))
            if bad:
                lib.update_doc(doc_id, tags=["from-image", "check-blurry", *meta.get("tags", [])])
            agent.update_item(match, status="done", doc=doc_id, docTitle=title, stats=stats, warning=warning,
                              stage=f"Rebuilt {len(paths)} page{'s' if len(paths) > 1 else ''} as text and drawings")
        except Exception as e:
            agent.update_item(match, status="error", stage=f"Couldn't convert: {e}")


@app.get("/api/convert/{job}/thumb/{i}")
def convert_thumb(job: str, i: int):
    if not re.fullmatch(r"[\w-]+", job):
        raise HTTPException(400)
    p = CONVERT_DIR / job / f"{i:02d}.thumb.jpg"
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.post("/api/agent/model/start")
def agent_model_start(request: Request):
    if not is_local(request):
        raise HTTPException(403)
    agent.start_model()
    return {"ok": True}


@app.websocket("/api/agent/ws")
async def agent_ws(ws: WebSocket):
    if not ws_authorized(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    agent.loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()
    agent.clients.add(q)
    await ws.send_json({"op": "reset", "items": agent.items, "chat": agent.chat_info()})
    await ws.send_json({"op": "state", **agent.state()})

    async def pump():
        while True:
            await ws.send_json(await q.get())

    sender = asyncio.create_task(pump())
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "prompt" and str(msg.get("text", "")).strip():
                await asyncio.to_thread(agent.prompt, msg["text"].strip()[:8000], str(msg.get("context", ""))[:600])
            elif kind == "abort":
                await asyncio.to_thread(agent.abort)
            elif kind == "new":
                await asyncio.to_thread(agent.new_chat)
            elif kind == "open_chat" and re.fullmatch(r"[\w-]+", str(msg.get("id", ""))):
                await asyncio.to_thread(agent.open_chat, msg["id"])
            elif kind == "thinking" and msg.get("level") in ("off", "low", "medium", "high"):
                await asyncio.to_thread(agent.set_thinking, msg["level"])
            elif kind == "status":
                await ws.send_json({"op": "state", **agent.state()})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sender.cancel()
        agent.clients.discard(q)


@app.post("/api/categories")
def add_category(c: CategoryIn):
    name = lib.ensure_category(c.name, c.color)
    return {"name": name}


@app.patch("/api/categories/{name}")
def patch_category(name: str, c: CategoryPatch):
    try:
        return {"name": lib.rename_category(name, c.name or name, c.color)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/categories/{name}")
def delete_category(name: str):
    try:
        lib.delete_category(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/categories/order")
def order_categories(names: list[str]):
    lib.reorder_categories(names)
    return {"ok": True}


@app.post("/api/rescan")
def rescan():
    lib.scan()
    return lib.stats()


def lan_addresses() -> list[str]:
    addrs = []
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
        addrs = [a for a in out if "." in a and not a.startswith(("172.17.", "127."))]
    except Exception:
        pass
    if not addrs:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            addrs = [s.getsockname()[0]]
        except Exception:
            addrs = []
    # Tailscale (100.64.0.0/10) last: it works away from home too
    return sorted(addrs, key=lambda a: a.startswith("100."))


@app.get("/api/pairing")
def pairing(request: Request):
    if not is_local(request):
        raise HTTPException(403)
    links = []
    for a in lan_addresses():
        url = f"http://{a}:{PORT}/?key={ACCESS_KEY}"
        buf = io.StringIO()
        segno.make(url, error="m").save(buf, kind="svg", scale=6, border=2, dark="#1B1A17", light="#FFFFFF", xmldecl=False, svgns=True)
        links.append({"address": a, "url": url, "qr": buf.getvalue(), "tailscale": a.startswith("100.")})
    return {"links": links, "port": PORT}


@app.post("/api/pairing/reset")
def reset_pairing(request: Request):
    """Sign out every phone by changing the key."""
    global ACCESS_KEY
    if not is_local(request):
        raise HTTPException(403)
    ACCESS_KEY = secrets.token_urlsafe(18)
    lib.set_setting("access_key", ACCESS_KEY)
    return {"ok": True}


app.mount("/", StaticFiles(directory=STATIC), name="static")


def start_background():
    threading.Thread(target=lib.scan_loop, daemon=True).start()


def main():
    import uvicorn
    start_background()
    uvicorn.run(app, host=os.environ.get("SHELFIE_HOST", "0.0.0.0"), port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
