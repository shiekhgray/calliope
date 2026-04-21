import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import get_current_user
from app import models

router = APIRouter(prefix="/scanner", tags=["scanner"])

INDEXER_URL = "http://indexer:8001"

_scan_running = False
_scan_phase = None  # "scanning" | "indexing" | None


def _call_indexer():
    """Trigger indexer and block until it finishes. Silently skips if unavailable."""
    try:
        req = urllib.request.Request(f"{INDEXER_URL}/index", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=10)
        while True:
            time.sleep(3)
            with urllib.request.urlopen(f"{INDEXER_URL}/status", timeout=5) as r:
                status = json.loads(r.read())
            if not status.get("running"):
                break
    except Exception as e:
        print(f"Indexer unavailable: {e}", file=sys.stderr)


def _run_scan():
    global _scan_running, _scan_phase
    _scan_running = True
    _scan_phase = "scanning"
    try:
        script = Path(__file__).parent.parent.parent / "scripts" / "scan.py"
        subprocess.run([sys.executable, str(script)], check=True)
        _scan_phase = "indexing"
        _call_indexer()
    finally:
        _scan_running = False
        _scan_phase = None


@router.post("/trigger", status_code=202)
def trigger_scan(
    background_tasks: BackgroundTasks,
    _current_user: models.User = Depends(get_current_user),
):
    """Kick off a library scan in the background. Requires authentication."""
    global _scan_running
    if _scan_running:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    background_tasks.add_task(_run_scan)
    return {"status": "scan started"}


@router.get("/status")
def scan_status():
    result = {"running": _scan_running, "phase": _scan_phase}
    if _scan_phase == "indexing":
        try:
            with urllib.request.urlopen(f"{INDEXER_URL}/status", timeout=2) as r:
                idx = json.loads(r.read())
            result["indexed"] = idx.get("indexed", 0)
            result["to_index"] = idx.get("to_index", 0)
        except Exception:
            pass
    return result
