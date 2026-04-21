import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import get_current_user
from app import models

router = APIRouter(prefix="/scanner", tags=["scanner"])

_scan_running = False


def _run_scan():
    global _scan_running
    _scan_running = True
    try:
        script = Path(__file__).parent.parent.parent / "scripts" / "scan.py"
        subprocess.run([sys.executable, str(script)], check=True)
    finally:
        _scan_running = False


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
    return {"running": _scan_running}
