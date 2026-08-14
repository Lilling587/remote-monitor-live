#!/usr/bin/env python3
"""
stageye_host.py
===============
Run this on the FOH computer. It captures the screen every ~2 seconds
and uploads it to Supabase. The viewer webpage polls for new frames
automatically — no live connection needed from this script.

INSTALL (run once in a terminal):
    pip install mss pillow requests supabase pyautogui

AUTOSTART (Windows):
    Press Win+R → type  shell:startup  → press Enter
    Put a shortcut to stageye_start.bat in that folder
"""

import io
import time
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# ─── FILL IN THESE VALUES ────────────────────────────────────────────────────
SUPABASE_URL = "https://fxomeytrkhrzkpjkpfjt.supabase.co"
SUPABASE_KEY = "sb_publishable_q6INNOwUoe6f4kOMSPJ4XQ_miL4APfh"
ROOM         = "stora-salen"   # ← change per stage: "stora-salen" or "blackbox"
# ─────────────────────────────────────────────────────────────────────────────

CAPTURE_INTERVAL = 2.0   # seconds between frames (2.0 = 0.5 fps)
JPEG_QUALITY     = 40    # 1–95. Lower = faster upload, worse image quality.

# ─── IMPORTS ─────────────────────────────────────────────────────────────────
try:
    import requests
    import pyautogui
    from mss import mss
    from PIL import Image
    from supabase import create_client
except ImportError as e:
    print(f"\nMissing library: {e}")
    print("Run this first:  pip install mss pillow requests supabase pyautogui\n")
    sys.exit(1)

# ─── LOGGING ─────────────────────────────────────────────────────────────────
log_file = Path(__file__).with_name("stageye.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger("stageye")

# ─── SETUP ───────────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = False

# Used only for the host_status table update (plain HTTPS, not Realtime)
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── UPLOAD ──────────────────────────────────────────────────────────────────
def upload_frame(jpeg_bytes: bytes) -> int:
    """Upload the JPEG to this room's frame slot in Storage."""
    url = f"{SUPABASE_URL}/storage/v1/object/screen-frames/{ROOM}/latest.jpg"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "image/jpeg",
        "x-upsert":      "true",
        "cache-control": "no-cache",
    }
    ts = int(time.time() * 1000)
    r = requests.put(url, data=jpeg_bytes, headers=headers, timeout=15)
    r.raise_for_status()
    return ts

# ─── HOST STATUS ─────────────────────────────────────────────────────────────
_last_heartbeat = 0.0

def _update_host_status(connected: bool):
    """Write connection status to the host_status table (read by /host page)."""
    global _last_heartbeat
    if connected and time.time() - _last_heartbeat < 5:
        return
    try:
        sb.table("host_status").update({
            "is_connected": connected,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }).eq("room", ROOM).execute()
        _last_heartbeat = time.time()
    except Exception as e:
        log.warning(f"Host status update failed: {e}")

# ─── MAIN LOOP ───────────────────────────────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("StagEye host starting")
    log.info(f"Supabase: {SUPABASE_URL}")
    log.info(f"Room:     {ROOM}")
    log.info(f"Interval: {CAPTURE_INTERVAL}s  |  JPEG quality: {JPEG_QUALITY}")
    log.info("=" * 50)

    with mss() as sct:
        monitor = sct.monitors[1]
        log.info(f"Capturing: {monitor['width']}×{monitor['height']}px (primary monitor)")

        while True:
            loop_start = time.time()
            try:
                shot       = sct.grab(monitor)
                img        = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                buf        = io.BytesIO()
                img.save(buf, format="JPEG", quality=JPEG_QUALITY)
                jpeg_bytes = buf.getvalue()

                upload_frame(jpeg_bytes)
                _update_host_status(True)

                size_kb = len(jpeg_bytes) // 1024
                elapsed = (time.time() - loop_start) * 1000
                log.info(f"Frame sent — {size_kb} KB  ({elapsed:.0f} ms)")

            except requests.exceptions.RequestException as e:
                log.error(f"Upload failed (network?): {e}")
            except Exception as e:
                log.error(f"Unexpected error: {e}")

            elapsed   = time.time() - loop_start
            remaining = max(0.0, CAPTURE_INTERVAL - elapsed)
            time.sleep(remaining)


if __name__ == "__main__":
    try:
        main()
    finally:
        _update_host_status(False)
