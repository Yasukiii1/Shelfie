
pi runs with every built-in tool disabled and only the Shelfie extension loaded, working inside the
library folder. The bridge keeps a simple transcript per chat and streams changes to connected
clients (desktop window and iPhone see the same conversation).

Chat history: every chat has its own pi session file (so reopening a chat restores the model's
memory of it) plus a small JSON transcript for the UI, both under ~/Shelfie/.shelfie/chats.
A new chat is a fresh pi session with no memory of anything else.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
EXTENSION = HERE / "shelfie-tools.ts"

PI_BIN = os.environ.get("SHELFIE_PI") or shutil.which("pi") or str(Path.home() / ".npm-global/bin/pi")
PROVIDER = os.environ.get("SHELFIE_PROVIDER", "llama-cpp")
MODEL = os.environ.get("SHELFIE_MODEL", "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp")
LLAMA_URL = os.environ.get("SHELFIE_LLAMA_URL", "http://127.0.0.1:8080")
LLAMA_CMD = os.environ.get("SHELFIE_LLAMA_CMD", (
    "~/ai/llama.cpp/build/bin/llama-server -m ~/models/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf "
    "--mmproj ~/models/mmproj-Qwen3.8-27B-F16.gguf --no-mmproj-offload "
    "--spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-sampling probabilistic -ngl all -fa on "
    "-ctk q8_0 -ctv q8_0 -ub 256 -b 1024 -c 32768 -np 1 --host 127.0.0.1 --port 8080"))

SYSTEM_PROMPT = """You are Shelfie's librarian: a helpful assistant living inside the user's private PDF library app.

What you can do, only through your tools:
- find and read the PDFs in the library (shelfie_list, shelfie_search, shelfie_read)
- create NEW PDF documents such as summaries, notes, study sheets (shelfie_create_pdf)
- create drawers and file/tag/star documents (shelfie_create_drawer, shelfie_organize)
You cannot delete, rename or overwrite anything, and you cannot see any file outside the library. If asked to, say so plainly.
Turning photos of pages into PDFs is done by the image button next to the message box, not by you.

Rules:
- Ground answers in the documents. Search or read before answering questions about their content, and cite documents as "Title" (#id, p. N).
- Read long PDFs in page ranges. Don't read whole books unless needed.
- Before creating a PDF or moving documents, make sure it's what the user asked for. Report what you created and where.
- Be concise. Use short paragraphs and lists. Plain Markdown only.
"""


def llama_status() -> str:
    try:
        with urllib.request.urlopen(LLAMA_URL + "/health", timeout=1.5) as r:
            return "online" if r.status == 200 else "loading"
    except urllib.error.HTTPError as e:
        return "loading" if e.code == 503 else "offline"
    except Exception:
        return "offline"


def llama_has_vision() -> bool:
    try:
        with urllib.request.urlopen(LLAMA_URL + "/props", timeout=2) as r:
            props = json.load(r)
        return bool((props.get("modalities") or {}).get("vision"))
    except Exception:
        return False


class Agent:
    def __init__(self, root: Path, port: int):
        self.root = root
        self.port = port
        self.proc: subprocess.Popen | None = None
        self.lock = threading.RLock()
        self.items: list[dict] = []
        self.busy = False
        self.thinking = "low"
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[asyncio.Queue] = set()
        self.chats_dir = root / ".shelfie" / "chats"
        self.sessions_dir = self.chats_dir / "pi-sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.log = root / ".shelfie" / "pi.log"
        self.llama_proc: subprocess.Popen | None = None
        self.chat: dict | None = None  # {id, title, created, updated, session}
        self._ids = itertools.count(1)
        self._pending: dict[str, tuple[threading.Event, list]] = {}

    # ---------- process ----------
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def ensure(self):
        with self.lock:
            if self.running():
                return
            cmd = [
                PI_BIN, "--mode", "rpc", "--session-dir", str(self.sessions_dir),
                "--provider", PROVIDER, "--model", MODEL, "--thinking", self.thinking,
                "--no-builtin-tools", "--no-extensions", "-e", str(EXTENSION),
                "--no-skills", "--no-context-files", "--no-mcp", "--no-prompt-templates", "--no-themes",
                "--offline", "--system-prompt", SYSTEM_PROMPT,
            ]
            if self.chat and self.chat.get("session") and Path(self.chat["session"]).exists():
                cmd += ["--session", self.chat["session"]]
            env = {**os.environ, "SHELFIE_URL": f"http://127.0.0.1:{self.port}", "PI_OFFLINE": "1"}
            env["PATH"] = os.pathsep.join([str(Path(PI_BIN).parent), "/usr/local/bin", "/usr/bin", env.get("PATH", "")])
            logf = open(self.log, "ab")
            self.proc = subprocess.Popen(cmd, cwd=self.root, env=env, stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE, stderr=logf, bufsize=0)
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def send(self, cmd: dict):
        self.ensure()
        with self.lock:
            self.proc.stdin.write((json.dumps(cmd) + "\n").encode())
            self.proc.stdin.flush()

    def request(self, cmd: dict, timeout: float = 15) -> dict | None:
        rid = f"s{next(self._ids)}"
        ev, box = threading.Event(), []
        self._pending[rid] = (ev, box)
        self.send({**cmd, "id": rid})
        ev.wait(timeout)
        self._pending.pop(rid, None)
        return box[0] if box else None

    # ---------- chats ----------
    def _chat_path(self, cid: str) -> Path:
        return self.chats_dir / f"{cid}.json"

    def save_chat(self):
        if not self.chat or not any(i["kind"] == "user" for i in self.items):
            return
        self.chat["updated"] = time.time()
        data = {**self.chat, "items": self.items, "thinking": self.thinking}
        tmp = self._chat_path(self.chat["id"]).with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(self._chat_path(self.chat["id"]))

    def list_chats(self) -> list[dict]:
        out = []
        for p in self.chats_dir.glob("*.json"):
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            out.append({"id": d["id"], "title": d.get("title", "Chat"), "updated": d.get("updated", 0),
                        "messages": sum(1 for i in d.get("items", []) if i["kind"] == "user")})
        return sorted(out, key=lambda c: -c["updated"])

    def _record_session(self):
        st = self.request({"type": "get_state"}, timeout=10)
        if st and st.get("success") and self.chat:
            sf = (st.get("data") or {}).get("sessionFile")
            if sf:
                self.chat["session"] = sf
        self.save_chat()
        self._broadcast({"op": "chats"})

    def new_chat(self):
        if self.running():
            if self.busy:
                self.send({"type": "abort"})
            self.request({"type": "new_session"}, timeout=10)
        self.save_chat()
        self.chat = None
        self.items = []
        self._broadcast({"op": "reset", "items": [], "chat": None})

    def open_chat(self, cid: str):
        p = self._chat_path(cid)
        if not p.exists():
            return
        d = json.loads(p.read_text())
        if self.busy and self.running():
            self.send({"type": "abort"})
        self.save_chat()
        self.chat = {k: d[k] for k in ("id", "title", "created", "updated") if k in d}
        self.chat["session"] = d.get("session")
        self.items = d.get("items", [])
        for it in self.items:  # nothing can still be running in a saved chat
            if it.get("status") == "running":
                it["status"] = "error"
        if self.chat.get("session") and Path(self.chat["session"]).exists():
            if self.running():
                self.request({"type": "switch_session", "sessionPath": self.chat["session"]}, timeout=15)
            # if pi isn't running yet, ensure() will start it with --session
        elif self.running():
            self.request({"type": "new_session"}, timeout=10)
        self._broadcast({"op": "reset", "items": self.items, "chat": self.chat_info()})

    def delete_chat(self, cid: str):
        p = self._chat_path(cid)
        if p.exists():
            try:
                sess = json.loads(p.read_text()).get("session")
                if sess and Path(sess).resolve().is_relative_to(self.sessions_dir.resolve()):
                    Path(sess).unlink(missing_ok=True)
            except Exception:
                pass
            p.unlink()
        if self.chat and self.chat["id"] == cid:
            self.chat = None
            self.items = []
            if self.running():
                self.request({"type": "new_session"}, timeout=10)
            self._broadcast({"op": "reset", "items": [], "chat": None})
        self._broadcast({"op": "chats"})

    def chat_info(self):
        return {"id": self.chat["id"], "title": self.chat["title"]} if self.chat else None

    # ---------- public actions ----------
    def prompt(self, text: str, context: str = ""):
        if llama_status() != "online":
            self._push({"kind": "error", "text": "The model isn't running. Start it from the assistant panel, then try again."})
            return
        if not self.chat:
            title = re.sub(r"\s+", " ", text).strip()
            self.chat = {"id": time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid() % 1000}",
                         "title": title[:70] + ("…" if len(title) > 70 else ""), "created": time.time(), "updated": time.time()}
            self._broadcast({"op": "chat", "chat": self.chat_info()})
        self._push({"kind": "user", "text": text, "t": time.time()})
        jobs = [i for i in self.items if i["kind"] == "convert"]
        if jobs:
            j = jobs[-1]
            state = {"running": f"is still running ({j.get('stage', '')})", "done": f"finished and created the PDF \"{j.get('docTitle', '')}\" (#{j.get('doc')}) in drawer {j.get('drawer')}",
                     "error": f"failed: {j.get('stage', '')}"}.get(j.get("status"), "")
            context = (context + "\n" if context else "") + (
                f"[Shelfie: the user attached {j.get('pages', 1)} photo(s) in this chat and Shelfie's photo-to-PDF converter {state}. "
                "That conversion is automatic; don't ask what to convert. If it's done you can read the new PDF with your tools.]")
        message = f"{context}\n\n{text}" if context else text
        self._set_busy(True)
        self.send({"type": "prompt", "message": message, "streamingBehavior": "followUp"})

    def abort(self):
        if self.running():
            self.send({"type": "abort"})

    def set_thinking(self, level: str):
        self.thinking = level
        if self.running():
            self.send({"type": "set_thinking_level", "level": level})
        self._broadcast({"op": "state", **self.state()})

    def state(self) -> dict:
        return {"busy": self.busy, "thinking": self.thinking, "model": llama_status(), "model_name": MODEL,
                "chat": self.chat_info()}

    def start_model(self):
        if llama_status() != "offline" or (self.llama_proc and self.llama_proc.poll() is None):
            return
        logp = self.root / ".shelfie" / "llama-server.log"
        cmd = os.path.expanduser(LLAMA_CMD).replace(" ~/", " " + str(Path.home()) + "/")
        if shutil.which("systemd-run"):
            # its own user unit, so restarting/updating Shelfie's service never kills the model
            subprocess.run(["systemctl", "--user", "reset-failed", "shelfie-llama.service"], capture_output=True)
            self.llama_proc = subprocess.Popen(
                ["systemd-run", "--user", "--unit=shelfie-llama", "--collect", "--quiet", f"--working-directory={Path.home()}",
                 "/bin/sh", "-c", f"exec {cmd} >> '{logp}' 2>&1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            log = open(logp, "ab")
            self.llama_proc = subprocess.Popen(cmd, shell=True, cwd=Path.home(), stdout=log, stderr=log, start_new_session=True)

    # ---------- items pushed by other features (image → PDF jobs) ----------
    def push_item(self, item: dict) -> int:
        if not self.chat:
            self.chat = {"id": time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid() % 1000}",
                         "title": item.get("title", "Converted images"), "created": time.time(), "updated": time.time()}
            self._broadcast({"op": "chat", "chat": self.chat_info()})
        self._push(item)
        return len(self.items) - 1

    def update_item(self, match: dict, **fields):
        for i in range(len(self.items) - 1, -1, -1):
            it = self.items[i]
            if all(it.get(k) == v for k, v in match.items()):
                it.update(fields)
                self._broadcast({"op": "set", "i": i, "item": it})
                if fields.get("status") in ("done", "error"):
                    self.save_chat()
                    self._broadcast({"op": "chats"})
                return

    # ---------- streaming ----------
    def _read(self, proc: subprocess.Popen):
        buf = b""
        while True:
            chunk = proc.stdout.read(65536) if proc.stdout else b""
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                raw = raw.rstrip(b"\r")
                if not raw:
                    continue
                try:
                    self._event(json.loads(raw))
                except Exception as e:
                    print("agent event error:", e)
        if self.busy:
            self._push({"kind": "error", "text": "The assistant stopped unexpectedly. See ~/Shelfie/.shelfie/pi.log"})
        self._set_busy(False)

    def _last(self, kind: str):
        for i in range(len(self.items) - 1, -1, -1):
            if self.items[i]["kind"] == kind:
                return i
            if self.items[i]["kind"] == "user":
                return None
        return None

    def _event(self, ev: dict):
        t = ev.get("type")
        if t == "response":
            rid = ev.get("id")
            if rid and rid in self._pending:
                e, box = self._pending[rid]
                box.append(ev)
                e.set()
                return
            if not ev.get("success") and ev.get("command") == "prompt":
                self._push({"kind": "error", "text": ev.get("error", "Prompt failed")})
                self._set_busy(False)
            return
        if t == "message_start" and (ev.get("message") or {}).get("role") == "assistant":
            self._push({"kind": "assistant", "text": "", "thinking": ""})
        elif t == "message_update":
            u = ev.get("assistantMessageEvent") or {}
            i = self._last("assistant")
            if i is None:
                self._push({"kind": "assistant", "text": "", "thinking": ""}); i = len(self.items) - 1
            if u.get("type") == "text_delta":
                self.items[i]["text"] += u.get("delta", "")
                self._broadcast({"op": "append", "i": i, "field": "text", "delta": u.get("delta", "")})
            elif u.get("type") == "thinking_delta":
                self.items[i]["thinking"] += u.get("delta", "")
                self._broadcast({"op": "append", "i": i, "field": "thinking", "delta": u.get("delta", "")})
        elif t == "message_end":
            m = ev.get("message") or {}
            if m.get("role") != "assistant":
                return
            i = self._last("assistant")
            if i is not None and isinstance(m.get("content"), list):
                txt = "".join(b.get("text", "") for b in m["content"] if b.get("type") == "text")
                th = "".join(b.get("thinking", "") for b in m["content"] if b.get("type") == "thinking")
                self.items[i].update(text=txt, thinking=th)
                self._broadcast({"op": "set", "i": i, "item": self.items[i]})
                if not txt.strip() and not th.strip():
                    self.items.pop(i)
                    self._broadcast({"op": "reset", "items": self.items, "chat": self.chat_info()})
            if m.get("stopReason") == "error" or m.get("errorMessage"):
                self._push({"kind": "error", "text": m.get("errorMessage") or "The model returned an error."})
        elif t == "tool_execution_start":
            self._push({"kind": "tool", "id": ev.get("toolCallId"), "name": ev.get("toolName"),
                        "args": ev.get("args") or {}, "status": "running"})
        elif t == "tool_execution_end":
            for i in range(len(self.items) - 1, -1, -1):
                it = self.items[i]
                if it["kind"] == "tool" and it.get("id") == ev.get("toolCallId"):
                    res = ev.get("result") or {}
                    content = res.get("content") if isinstance(res, dict) else None
                    summary = ""
                    if isinstance(content, list):
                        summary = " ".join(c.get("text", "") for c in content if c.get("type") == "text")
                    it.update(status="error" if ev.get("isError") else "done",
                              summary=summary[:400], details=(res.get("details") if isinstance(res, dict) else None) or {})
                    self._broadcast({"op": "set", "i": i, "item": it})
                    break
        elif t == "agent_start":
            self._set_busy(True)
        elif t == "agent_settled":
            self._set_busy(False)
            threading.Thread(target=self._record_session, daemon=True).start()
        elif t == "extension_error":
            self._push({"kind": "error", "text": f"Tool error: {ev.get('error')}"})

    def _push(self, item: dict):
        self.items.append(item)
        self._broadcast({"op": "push", "item": item})

    def _set_busy(self, b: bool):
        if self.busy != b:
            self.busy = b
            self._broadcast({"op": "state", **self.state()})

    def _broadcast(self, msg: dict):
        if not self.loop:
            return
        for q in list(self.clients):
            self.loop.call_soon_threadsafe(q.put_nowait, msg)
