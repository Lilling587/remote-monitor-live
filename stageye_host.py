#!/usr/bin/env python3
"""
stageye_host.py
===============
Run this on the FOH computer. It captures the screen every second,
uploads it to Supabase, and relays mouse/keyboard control from viewers.

INSTALL (run once in a terminal):
    pip install mss pillow requests supabase pyautogui

AUTOSTART (Windows):
    Press Win+R → type  shell:startup  → press Enter
    Put a shortcut to stageye_start.bat in that folder
"""

import io
import time
import threading
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# ─── FILL IN THESE TWO VALUES ────────────────────────────────────────────────
#  Find them at:  https://your-app.lovable.app/host
SUPABASE_URL = "https://fxomeytrkhrzkpjkpfjt.supabase.co"
SUPABASE_KEY = "sb_publishable_q6INNOwUoe6f4kOMSPJ4XQ_miL4APfh"
# ─────────────────────────────────────────────────────────────────────────────

CAPTURE_INTERVAL = 1.0   # seconds between frames  (1.0 = 1 frame per second)
JPEG_QUALITY     = 55    # 1–95. Lower = faster upload, worse image quality.
                         # 55 is a good balance for SPL meter monitoring.

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

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

BUTTON_MAP = {0: "left", 1: "middle", 2: "right"}

KEY_MAP = {
    "Enter": "enter",     "Escape": "esc",       " ": "space",
    "Backspace": "backspace", "Tab": "tab",       "Delete": "delete",
    "ArrowUp": "up",      "ArrowDown": "down",
    "ArrowLeft": "left",  "ArrowRight": "right",
    "Home": "home",       "End": "end",
    "F1": "f1", "F2": "f2", "F3": "f3",  "F4": "f4",
    "F5": "f5", "F6": "f6", "F7": "f7",  "F8": "f8",
    "F9": "f9", "F10": "f10", "F11": "f11", "F12": "f12",
}

# ─── UPLOAD ──────────────────────────────────────────────────────────────────
def upload_frame(jpeg_bytes: bytes) -> int:
    url = f"{SUPABASE_URL}/storage/v1/object/screen-frames/latest.jpg"
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

# ─── REALTIME ────────────────────────────────────────────────────────────────
_frame_channel = None
_channel_ready = threading.Event()

def broadcast_new_frame(ts: int):
    if _frame_channel and _channel_ready.is_set():
        try:
            _frame_channel.send_broadcast("frame", {"timestamp": ts})
        except Exception as e:
            log.warning(f"Broadcast skipped: {e}")

# ─── CONTROL EVENTS ──────────────────────────────────────────────────────────
def on_control_event(payload):
    try:
        e    = payload.get("payload", payload)
        w, h = pyautogui.size()
        kind = e.get("type")

        if kind in ("mousemove", "mouseclick"):
            x = int(float(e["x"]) * w)
            y = int(float(e["y"]) * h)
            pyautogui.moveTo(x, y, _pause=False)
            log.info(f"Mouse → ({x}, {y})")

        if kind == "mouseclick":
            btn = BUTTON_MAP.get(int(e.get("button", 0)), "left")
            pyautogui.click(button=btn, _pause=False)
            log.info(f"Click {btn}")

        elif kind == "keydown":
            raw = e.get("key", "")
            key = KEY_MAP.get(raw) or (raw.lower() if len(raw) == 1 else None)
            if key:
                pyautogui.press(key, _pause=False)
                log.info(f"Key: {raw!r} → {key}")

    except Exception as exc:
        log.warning(f"Control event error: {exc}")

# ─── REALTIME THREAD ─────────────────────────────────────────────────────────
def realtime_thread():
    global _frame_channel
    while True:
        try:
            log.info("Realtime: connecting...")
            _channel_ready.clear()

            frame_ch = sb.channel("frame-updates")
            frame_ch.subscribe()
            _frame_channel = frame_ch

            ctrl_ch = sb.channel("control-events")
            ctrl_ch.on_broadcast("control", on_control_event)
            ctrl_ch.subscribe()

            _channel_ready.set()
            log.info("Realtime: connected ✓")

            while True:
                time.sleep(5)

        except Exception as e:
            log.error(f"Realtime disconnected: {e}. Reconnecting in 10s...")
            _channel_ready.clear()
            _frame_channel = None
            time.sleep(10)

# ─── HOST STATUS ─────────────────────────────────────────────────────────────
_last_heartbeat = 0.0

def _update_host_status(connected: bool):
    """Write connection status to the host_status table (read by /host page)."""
    global _last_heartbeat
    # Only write every 5 seconds to avoid hammering the database
    if connected and time.time() - _last_heartbeat < 5:
        return
    try:
        sb.table("host_status").update({
            "is_connected": connected,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", 1).execute()
        _last_heartbeat = time.time()
    except Exception as e:
        log.warning(f"Host status update failed: {e}")

# ─── MAIN LOOP ───────────────────────────────────────────────────────────────
def main():
    if "YOUR_PROJECT" in SUPABASE_URL or "YOUR_ANON_KEY" in SUPABASE_KEY:
        log.error("Fill in SUPABASE_URL and SUPABASE_KEY at the top of this file.")
        log.error("Find them at: https://your-app.lovable.app/host")
        sys.exit(1)

    log.info("=" * 50)
    log.info("StagEye host starting")
    log.info(f"Supabase: {SUPABASE_URL}")
    log.info(f"Interval: {CAPTURE_INTERVAL}s  |  JPEG quality: {JPEG_QUALITY}")
    log.info("=" * 50)

    t = threading.Thread(target=realtime_thread, daemon=True, name="realtime")
    t.start()

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

                ts      = upload_frame(jpeg_bytes)
                broadcast_new_frame(ts)

                # Heartbeat — keeps the /host page status dot green
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
