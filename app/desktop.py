"""Shelfie desktop window. Uses the always-on background service if it's running,
otherwise starts the server inside this process."""
from __future__ import annotations

import os
import threading
import time
import urllib.request

PORT = int(os.environ.get("SHELFIE_PORT", "8642"))
URL = f"http://127.0.0.1:{PORT}/"


def server_up() -> bool:
    try:
        with urllib.request.urlopen(URL + "api/version", timeout=1) as r:
            return r.status == 200
    except Exception:
        return False


def ensure_server():
    if server_up():
        return
    from . import server
    import uvicorn

    server.start_background()
    cfg = uvicorn.Config(server.app, host=os.environ.get("SHELFIE_HOST", "0.0.0.0"), port=PORT, log_level="warning")
    threading.Thread(target=uvicorn.Server(cfg).run, daemon=True).start()
    for _ in range(100):
        if server_up():
            return
        time.sleep(0.1)


def main():
    ensure_server()
    # Name the process "shelfie" so the dock matches this window to shelfie.desktop
    # (otherwise Wayland sees "python" and shows a generic gear icon).
    from gi.repository import GLib
    GLib.set_prgname("shelfie")
    GLib.set_application_name("Shelfie")
    import webview

    webview.create_window("Shelfie", URL, width=1320, height=860, min_size=(820, 560),
                          background_color="#F3EFE6", text_select=True, js_api=DesktopApi())
    from pathlib import Path
    icon = Path(__file__).parent / "static" / "icons" / "icon-256.png"
    webview.start(_tune_webkit, gui="gtk", private_mode=False, icon=str(icon))


class DesktopApi:
    """Called from the page as window.pywebview.api.* (desktop window only)."""

    def clipboard_image(self):
        """Return the image on the system clipboard as base64 PNG, or {} if there isn't one.
        Covers screenshots and images copied in Files/image viewers, which WebKit doesn't always expose."""
        import base64
        import threading
        from gi.repository import GLib, Gdk, Gtk

        box, done = {}, threading.Event()

        def read():
            try:
                pix = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_image()
                if pix is not None:
                    ok, buf = pix.save_to_bufferv("png", [], [])
                    if ok:
                        box["data"] = base64.b64encode(buf).decode()
                        box["width"], box["height"] = pix.get_width(), pix.get_height()
            except Exception as e:
                box["error"] = str(e)
            done.set()
            return False

        GLib.idle_add(read)  # GTK must be touched on its main thread
        done.wait(5)
        return box

    def clipboard_files(self):
        """PDFs/images on the system clipboard: files copied in the Files app (as URIs) or a copied image.
        Returns [{name, type, data(base64)}]. Only PDFs and images are read, max 20 files / 80 MB each."""
        import base64
        import mimetypes
        import threading
        import urllib.parse
        from pathlib import Path
        from gi.repository import GLib, Gdk, Gtk

        uris, done = [], threading.Event()

        def read():
            try:
                cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                got = cb.wait_for_uris()
                if not got:
                    txt = cb.wait_for_text() or ""
                    got = [l.strip() for l in txt.splitlines() if l.strip().startswith("file://")]
                uris.extend(got or [])
            except Exception:
                pass
            done.set()
            return False

        GLib.idle_add(read)
        done.wait(5)
        out = []
        for u in uris[:20]:
            if not u.startswith("file://"):
                continue
            p = Path(urllib.parse.unquote(urllib.parse.urlparse(u).path))
            mime = mimetypes.guess_type(p.name)[0] or ""
            if not p.is_file() or not (mime == "application/pdf" or mime.startswith("image/")) or p.stat().st_size > 80 << 20:
                continue
            out.append({"name": p.name, "type": mime, "data": base64.b64encode(p.read_bytes()).decode()})
        if not out:
            img = self.clipboard_image()
            if img.get("data"):
                out.append({"name": "", "type": "image/png", "data": img["data"]})
        return out


def _tune_webkit():
    """Turn on WebKit's smooth scrolling for the window."""
    from gi.repository import GLib

    def apply():
        try:
            from webview.platforms.gtk import BrowserView
            for view in BrowserView.instances.values():
                st = view.webview.get_settings()
                st.set_enable_smooth_scrolling(True)
        except Exception as e:
            print("webkit tuning skipped:", e)
        return False

    GLib.timeout_add(300, apply)


if __name__ == "__main__":
    main()
