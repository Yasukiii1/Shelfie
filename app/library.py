from __future__ import annotations

import os
import queue
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

INBOX = "Inbox"
PALETTE = ["#C2410C", "#B7791F", "#4D7C0F", "#0F766E", "#1D4ED8", "#7C3AED", "#BE185D", "#57534E"]
TEXT_PAGE_LIMIT = 40
TEXT_CHAR_LIMIT = 300_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '',
  favorite INTEGER NOT NULL DEFAULT 0,
  pages INTEGER NOT NULL DEFAULT 0,
  size INTEGER NOT NULL DEFAULT 0,
  added REAL NOT NULL,
  mtime REAL NOT NULL DEFAULT 0,
  opened REAL NOT NULL DEFAULT 0,
  processed REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS categories (
  name TEXT PRIMARY KEY,
  color TEXT NOT NULL,
  sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(title, tags, body, tokenize='unicode61 remove_diacritics 2');
"""

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def clean_name(name: str, fallback: str = "Untitled") -> str:
    name = _BAD.sub(" ", name).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    return name[:120] or fallback


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 2
    while True:
        cand = path.with_name(f"{stem} ({n}){suffix}")
        if not cand.exists():
            return cand
        n += 1


class Library:
    def __init__(self, root: Path):
        self.root = root
        self.meta = root / ".shelfie"
        self.thumbs = self.meta / "thumbs"
        self.trash = self.meta / "trash"
        for d in (root, self.meta, self.thumbs, self.trash, root / INBOX):
            d.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.meta / "index.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.jobs: queue.Queue[int] = queue.Queue()
        self.version = 0  # bumps on every change, lets clients poll cheaply
        threading.Thread(target=self._worker, daemon=True).start()

    # ---------- helpers ----------
    def q(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            self.version += 1
            return cur

    def setting(self, key, default=None):
        rows = self.q("SELECT value FROM settings WHERE key=?", (key,))
        return rows[0]["value"] if rows else default

    def set_setting(self, key, value):
        self.x("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))

    def abs(self, rel: str) -> Path:
        return self.root / rel

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    # ---------- categories ----------
    def ensure_category(self, name: str, color: str | None = None) -> str:
        name = clean_name(name, INBOX)
        (self.root / name).mkdir(exist_ok=True)
        if not self.q("SELECT 1 FROM categories WHERE name=?", (name,)):
            n = self.q("SELECT COUNT(*) c FROM categories")[0]["c"]
            if name == INBOX:
                color = color or "#78716C"
            self.x("INSERT INTO categories(name,color,sort) VALUES(?,?,?)",
                   (name, color or PALETTE[n % len(PALETTE)], 0 if name == INBOX else n + 1))
        return name

    def categories(self):
        rows = self.q("""
          SELECT c.name, c.color, c.sort, COUNT(d.id) count, COALESCE(SUM(d.pages),0) pages,
                 COALESCE(SUM(d.size),0) size
          FROM categories c LEFT JOIN docs d ON d.category=c.name
          GROUP BY c.name ORDER BY (c.name<>'Inbox'), c.sort, c.name COLLATE NOCASE""")
        return [dict(r) for r in rows]

    def rename_category(self, old: str, new: str, color: str | None = None):
        new = clean_name(new)
        if old == INBOX and new != INBOX:
            raise ValueError("Inbox can't be renamed")
        if new != old:
            if (self.root / new).exists():
                raise ValueError("A drawer with that name already exists")
            with self.lock:
                (self.root / old).rename(self.root / new)
                self.db.execute("UPDATE categories SET name=? WHERE name=?", (new, old))
                for r in self.db.execute("SELECT id,path FROM docs WHERE category=?", (old,)).fetchall():
                    newpath = new + r["path"][len(old):]
                    self.db.execute("UPDATE docs SET path=?, category=? WHERE id=?", (newpath, new, r["id"]))
                self.db.commit()
        if color:
            self.x("UPDATE categories SET color=? WHERE name=?", (color, new))
        self.version += 1
        return new

    def delete_category(self, name: str):
        if name == INBOX:
            raise ValueError("Inbox can't be deleted")
        for r in self.q("SELECT id FROM docs WHERE category=?", (name,)):
            self.move_doc(r["id"], INBOX)
        folder = self.root / name
        if folder.exists():
            leftovers = [p for p in folder.rglob("*") if p.is_file()]
            if leftovers:
                dest = unique_path(self.trash / name)
                shutil.move(str(folder), dest)
            else:
                shutil.rmtree(folder)
        self.x("DELETE FROM categories WHERE name=?", (name,))

    def reorder_categories(self, names: list[str]):
        with self.lock:
            for i, n in enumerate(names):
                self.db.execute("UPDATE categories SET sort=? WHERE name=?", (i + 1, n))
            self.db.commit()
            self.version += 1

    # ---------- documents ----------
    def doc(self, doc_id: int):
        rows = self.q("SELECT * FROM docs WHERE id=?", (doc_id,))
        return dict(rows[0]) if rows else None

    def list_docs(self, category=None, tag=None, starred=False, sort="added", q=None):
        order = {
            "added": "d.added DESC", "title": "d.title COLLATE NOCASE ASC",
            "opened": "d.opened DESC", "size": "d.size DESC", "pages": "d.pages DESC",
        }.get(sort, "d.added DESC")
        where, args = [], []
        if category:
            where.append("d.category=?"); args.append(category)
        if starred:
            where.append("d.favorite=1")
        if sort == "opened":
            where.append("d.opened>0")
        if tag:
            where.append("(','||d.tags||',') LIKE ?"); args.append(f"%,{tag},%")
        if q:
            match = self._fts_query(q)
            if not match:
                return []
            sql = f"""SELECT d.*, snippet(docs_fts, 2, char(2), char(3), '…', 14) snippet
                      FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid
                      WHERE docs_fts MATCH ? {'AND ' + ' AND '.join(where) if where else ''}
                      ORDER BY bm25(docs_fts, 8.0, 4.0, 1.0) LIMIT 200"""
            return [dict(r) for r in self.q(sql, [match, *args])]
        sql = f"SELECT d.* FROM docs d {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY {order}"
        return [dict(r) for r in self.q(sql, args)]

    @staticmethod
    def _fts_query(q: str) -> str:
        toks = re.findall(r"\w+", q, re.UNICODE)
        return " ".join(f'"{t}"*' for t in toks)

    def tags(self):
        counts: dict[str, int] = {}
        for r in self.q("SELECT tags FROM docs WHERE tags<>''"):
            for t in r["tags"].split(","):
                if t:
                    counts[t] = counts.get(t, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    def add_file(self, src_name: str, data_path: Path, category: str) -> int:
        with self.lock:
            return self._add_file(src_name, data_path, category)

    def _add_file(self, src_name: str, data_path: Path, category: str) -> int:
        category = self.ensure_category(category or INBOX)
        name = clean_name(Path(src_name).stem) + ".pdf"
        dest = unique_path(self.root / category / name)
        shutil.move(str(data_path), dest)
        return self._index_new(dest)

    def _index_new(self, path: Path) -> int:
        st = path.stat()
        rel = self.rel(path)
        category = rel.split("/", 1)[0]
        self.ensure_category(category)
        cur = self.x("""INSERT INTO docs(path,title,category,size,added,mtime) VALUES(?,?,?,?,?,?)""",
                     (rel, path.stem, category, st.st_size, time.time(), st.st_mtime))
        doc_id = cur.lastrowid
        self.x("INSERT INTO docs_fts(rowid,title,tags,body) VALUES(?,?,?,?)", (doc_id, path.stem, "", ""))
        self.jobs.put(doc_id)
        return doc_id

    def update_doc(self, doc_id: int, title=None, category=None, tags=None, favorite=None):
        d = self.doc(doc_id)
        if not d:
            raise KeyError(doc_id)
        if category is not None and category != d["category"]:
            self.move_doc(doc_id, category)
            d = self.doc(doc_id)
        if title is not None and title.strip() and title.strip() != d["title"]:
            title = title.strip()
            src = self.abs(d["path"])
            dest = unique_path(src.with_name(clean_name(title) + ".pdf"))
            src.rename(dest)
            self.x("UPDATE docs SET title=?, path=? WHERE id=?", (title, self.rel(dest), doc_id))
        if tags is not None:
            tl = []
            for t in tags:
                t = re.sub(r"[,\s]+", "-", t.strip().lower()).strip("-")
                if t and t not in tl:
                    tl.append(t)
            self.x("UPDATE docs SET tags=? WHERE id=?", (",".join(tl), doc_id))
        if favorite is not None:
            self.x("UPDATE docs SET favorite=? WHERE id=?", (1 if favorite else 0, doc_id))
        d = self.doc(doc_id)
        self.x("UPDATE docs_fts SET title=?, tags=? WHERE rowid=?", (d["title"], d["tags"].replace(",", " "), doc_id))
        return d

    def move_doc(self, doc_id: int, category: str):
        d = self.doc(doc_id)
        category = self.ensure_category(category)
        src = self.abs(d["path"])
        dest = unique_path(self.root / category / src.name)
        shutil.move(str(src), dest)
        self.x("UPDATE docs SET path=?, category=? WHERE id=?", (self.rel(dest), category, doc_id))

    def delete_doc(self, doc_id: int):
        d = self.doc(doc_id)
        if not d:
            return
        src = self.abs(d["path"])
        if src.exists():
            shutil.move(str(src), unique_path(self.trash / src.name))
        self._forget(doc_id)

    def _forget(self, doc_id: int):
        self.x("DELETE FROM docs WHERE id=?", (doc_id,))
        self.x("DELETE FROM docs_fts WHERE rowid=?", (doc_id,))
        (self.thumbs / f"{doc_id}.jpg").unlink(missing_ok=True)

    def mark_opened(self, doc_id: int):
        self.x("UPDATE docs SET opened=? WHERE id=?", (time.time(), doc_id))

    def stats(self):
        r = self.q("SELECT COUNT(*) n, COALESCE(SUM(pages),0) pages, COALESCE(SUM(size),0) size, "
                   "COALESCE(SUM(favorite),0) starred FROM docs")[0]
        pending = self.q("SELECT COUNT(*) c FROM docs WHERE processed=0")[0]["c"]
        return {**dict(r), "pending": pending, "version": self.version, "root": str(self.root)}

    # ---------- disk sync ----------
    def scan(self):
        """Reconcile the index with what's actually on disk."""
        with self.lock:
            self._scan()

    def _scan(self):
        # loose PDFs in the root go to the Inbox
        for p in self.root.glob("*"):
            if p.is_file() and p.suffix.lower() == ".pdf":
                shutil.move(str(p), unique_path(self.root / INBOX / p.name))
        for d in self.root.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                self.ensure_category(d.name)
        known = {r["path"]: dict(r) for r in self.q("SELECT id,path,mtime,size FROM docs")}
        seen = set()
        for p in self.root.rglob("*"):
            if p.suffix.lower() != ".pdf" or not p.is_file():
                continue
            rel = self.rel(p)
            if rel.startswith(".") or "/." in rel or rel.count("/") == 0:
                continue
            seen.add(rel)
            k = known.get(rel)
            if not k:
                self._index_new(p)
            else:
                st = p.stat()
                if abs(st.st_mtime - k["mtime"]) > 1 or st.st_size != k["size"]:
                    self.x("UPDATE docs SET mtime=?, size=?, processed=0 WHERE id=?", (st.st_mtime, st.st_size, k["id"]))
                    self.jobs.put(k["id"])
        for rel, k in known.items():
            if rel not in seen:
                self._forget(k["id"])
        # categories whose folder vanished
        for c in self.q("SELECT name FROM categories"):
            if not (self.root / c["name"]).is_dir() and c["name"] != INBOX:
                self.x("DELETE FROM categories WHERE name=?", (c["name"],))
        for r in self.q("SELECT id FROM docs WHERE processed=0"):
            self.jobs.put(r["id"])

    def scan_loop(self, every=30):
        while True:
            try:
                self.scan()
            except Exception as e:  # never let the watcher die
                print("scan error:", e)
            time.sleep(every)

    # ---------- background processing ----------
    def _worker(self):
        while True:
            doc_id = self.jobs.get()
            try:
                self._process(doc_id)
            except Exception as e:
                print("process error", doc_id, e)
                self.x("UPDATE docs SET processed=? WHERE id=?", (time.time(), doc_id))

    def _process(self, doc_id: int):
        d = self.doc(doc_id)
        if not d or d["processed"]:
            return
        path = self.abs(d["path"])
        if not path.exists():
            return
        pages, title = 0, None
        info = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=60)
        for line in info.stdout.splitlines():
            if line.startswith("Pages:"):
                pages = int(line.split()[-1])
            elif line.startswith("Title:"):
                title = line.split(":", 1)[1].strip()
        out = self.thumbs / f"{doc_id}"
        subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", "quality=82", "-scale-to", "520",
                        "-f", "1", "-l", "1", "-singlefile", str(path), str(out)],
                       capture_output=True, timeout=120)
        txt = subprocess.run(["pdftotext", "-l", str(TEXT_PAGE_LIMIT), "-enc", "UTF-8", str(path), "-"],
                             capture_output=True, timeout=180)
        body = txt.stdout.decode("utf-8", "replace")[:TEXT_CHAR_LIMIT]
        body = re.sub(r"[ \t]+", " ", body)
        st = path.stat()
        self.x("UPDATE docs SET pages=?, size=?, mtime=?, processed=? WHERE id=?",
               (pages, st.st_size, st.st_mtime, time.time(), doc_id))
        d = self.doc(doc_id)
        meta_title = title if title and len(title) > 3 and not title.lower().startswith(("microsoft", "untitled")) else ""
        self.x("UPDATE docs_fts SET title=?, tags=?, body=? WHERE rowid=?",
               (d["title"] + (" " + meta_title if meta_title else ""), d["tags"].replace(",", " "), body, doc_id))
