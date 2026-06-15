"""Plain Python stdlib HTTP server for the similarity indexer.

Routes:
    POST /index       — start indexing (202 Accepted, 409 if already running)
    GET  /status      — {"running": bool, "indexed": int, "to_index": int}
    POST /map/rebuild — full UMAP re-fit of the Music Map atlas (202, 409 if busy)
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .index import run_indexing

_lock = threading.Lock()
_running = False
_indexed = 0
_to_index = 0


def _update_status(indexed=None, to_index=None):
    global _indexed, _to_index
    if indexed is not None:
        _indexed = indexed
    if to_index is not None:
        _to_index = to_index


def _run():
    global _running, _indexed, _to_index
    try:
        run_indexing(_update_status)
    except Exception as e:
        print(f"Indexer fatal error: {e}", file=sys.stderr, flush=True)
    finally:
        _running = False


def _run_map_rebuild():
    global _running
    try:
        from sqlalchemy.orm import Session
        from .database import engine
        from .mapping import build_map
        with Session(engine) as db:
            build_map(db, full_refit=True)
    except Exception as e:
        print(f"Map rebuild fatal error: {e}", file=sys.stderr, flush=True)
    finally:
        _running = False


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        global _running
        if self.path not in ("/index", "/map/rebuild"):
            self._json(404, {"error": "not found"})
            return
        with _lock:
            if _running:
                self._json(409, {"error": "already running"})
                return
            _running = True
        if self.path == "/map/rebuild":
            threading.Thread(target=_run_map_rebuild, daemon=True).start()
            self._json(202, {"status": "map rebuild started"})
        else:
            threading.Thread(target=_run, daemon=True).start()
            self._json(202, {"status": "indexing started"})

    def do_GET(self):
        if self.path != "/status":
            self._json(404, {"error": "not found"})
            return
        self._json(200, {"running": _running, "indexed": _indexed, "to_index": _to_index})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8001), _Handler)
    print("Indexer listening on :8001", flush=True)
    server.serve_forever()
