# Shelfie

A private, local-first PDF library for Linux desktop and iPhone. Shelfie stores documents on the host computer, indexes PDF text locally, and can use a local llama.cpp model for library questions and photo-to-PDF reconstruction.

## Requirements

- Python 3.11 or newer
- Poppler utilities: `pdfinfo`, `pdftoppm`, `pdftotext`, and `pdfunite`
- GTK 3 and WebKitGTK 4.1 for the desktop window (`pywebview`)
- A local llama.cpp server and the `pi` RPC agent for assistant and photo reconstruction features

## Install

Create and activate a virtual environment, then install Python dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Start the web service:

```sh
python -m app.server
```

Or launch the Linux desktop window:

```sh
python -m app.desktop
```

By default, Shelfie uses `~/Shelfie` for PDFs and its private index, listens on port `8642`, and binds to all network interfaces so a phone on the same network can pair. Set `SHELFIE_ROOT`, `SHELFIE_PORT`, or `SHELFIE_HOST` to change those defaults. The librarian model and executable settings can be configured with `SHELFIE_PI`, `SHELFIE_PROVIDER`, `SHELFIE_MODEL`, `SHELFIE_LLAMA_URL`, and `SHELFIE_LLAMA_CMD`.

## Data and privacy

The library folder contains personal documents and runtime data. Keep it outside this source repository. Shelfie generates an access key in the library's `.shelfie` metadata directory. The app is designed for local use; phone pairing currently uses HTTP on the local network.

## Included files

The `app/` tree contains the FastAPI service, SQLite-backed library index, PDF viewer, assistant bridge and tools, image conversion pipeline, and frontend assets. `requirements.txt` lists Python dependencies. PDF.js is vendored under `app/static/vendor/`; its license notice is retained in the distributed files.
