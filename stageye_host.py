#!/usr/bin/env python3
"""
StagEye host — FOH-datorns skript.

Gor tre saker samtidigt:
  1. Tar skarmbild kontinuerligt och haller senaste bilden i minnet
  2. Serverar en lokal viewer pa http://<FOH-IP>:8080/  (LAN-lage, kraver INTE internet)
  3. Laddar upp till Supabase Storage i bakgrunden (WAN-lage, misslyckas tyst om natet blockerar)

Kors med:  pythonw stageye_host.py   (via stageye_start.bat)
"""

import io
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mss
import requests
from PIL import Image

# =====================================================================
#  KONFIGURATION — andra har
# =====================================================================

ROOM = "stora-salen"                 # "stora-salen" eller "blackbox"
ROOM_LABEL = "Stora Salen"           # visas i viewern

SUPABASE_URL = "https://fxomeytrkhrzkpjkpfjt.supabase.co"
SUPABASE_KEY = "sb_publishable_q6INNOwUoe6f4kOMSPJ4XQ_miL4APfh"
BUCKET = "screen-frames"

LOCAL_PORT = 8080                    # porten LAN-viewern lyssnar pa
MONITOR = 1                          # 1 = primar skarm, 2 = andra skarmen osv.

LOCAL_INTERVAL = 0.4                 # sekunder mellan skarmbilder (LAN, gratis bandbredd)
CLOUD_INTERVAL = 2.0                 # sekunder mellan uppladdningar till Supabase
LOCAL_QUALITY = 65                   # JPEG-kvalitet lokalt
CLOUD_QUALITY = 40                   # JPEG-kvalitet till molnet

UPLOAD_ENABLED = True                # satt False for att kora helt utan internet
CONTROL_ENABLED = True               # mus/tangentbord fran LAN-viewern

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stageye_host.log")

# =====================================================================
#  Delat tillstand
# =====================================================================

_state_lock = threading.Lock()
_latest_jpeg = None          # bytes — senaste lokala bilden
_latest_seq = 0              # rakas upp for varje ny bild
_screen_size = (0, 0)        # (bredd, hojd) i pixlar
_last_upload_ok = None       # None = inte forsokt an, True/False efter forsta forsoket
_last_upload_time = 0.0
_started_at = time.time()


def log(message):
    """Skriver till loggfil. print() kan krascha under pythonw (ingen konsol)."""
    line = "%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def local_ip():
    """Tar reda pa datorns IP i LAN:et. Skickar ingen trafik."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


# =====================================================================
#  Trad 1 — skarmfangst
# =====================================================================

def capture_loop():
    global _latest_jpeg, _latest_seq, _screen_size

    with mss.mss() as sct:
        monitor = sct.monitors[MONITOR]
        while True:
            start = time.time()
            try:
                shot = sct.grab(monitor)
                image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=LOCAL_QUALITY)

                with _state_lock:
                    _latest_jpeg = buffer.getvalue()
                    _latest_seq += 1
                    _screen_size = image.size
            except Exception as exc:
                log("capture-fel: %s" % exc)
                time.sleep(2)

            elapsed = time.time() - start
            time.sleep(max(0.0, LOCAL_INTERVAL - elapsed))


# =====================================================================
#  Trad 2 — uppladdning till Supabase
# =====================================================================

def upload_loop():
    global _last_upload_ok, _last_upload_time

    url = "%s/storage/v1/object/%s/%s/latest.jpg" % (SUPABASE_URL, BUCKET, ROOM)
    headers = {
        "Authorization": "Bearer %s" % SUPABASE_KEY,
        "apikey": SUPABASE_KEY,
        "Content-Type": "image/jpeg",
        "x-upsert": "true",
        "Cache-Control": "no-cache",
    }

    while True:
        time.sleep(CLOUD_INTERVAL)
        if not UPLOAD_ENABLED:
            continue

        with _state_lock:
            jpeg = _latest_jpeg

        if jpeg is None:
            continue

        try:
            # Komprimera om till molnkvalitet for att spara bandbredd
            image = Image.open(io.BytesIO(jpeg))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=CLOUD_QUALITY)

            response = requests.put(url, headers=headers, data=buffer.getvalue(), timeout=10)
            ok = response.status_code in (200, 201)

            with _state_lock:
                if _last_upload_ok is not True and ok:
                    log("uppladdning fungerar igen")
                _last_upload_ok = ok
                if ok:
                    _last_upload_time = time.time()

            if not ok:
                log("uppladdning nekad: HTTP %s %s" % (response.status_code, response.text[:200]))
        except Exception as exc:
            with _state_lock:
                if _last_upload_ok is not False:
                    log("uppladdning misslyckas (LAN-laget paverkas inte): %s" % exc)
                _last_upload_ok = False


# =====================================================================
#  Fjarrstyrning (valfritt)
# =====================================================================

_pyautogui = None
if CONTROL_ENABLED:
    try:
        import pyautogui as _pyautogui
        _pyautogui.FAILSAFE = False
    except Exception as exc:
        log("pyautogui kunde inte laddas, styrning avstangd: %s" % exc)
        _pyautogui = None


def handle_control(payload):
    if _pyautogui is None:
        return False

    with _state_lock:
        width, height = _screen_size

    if width == 0 or height == 0:
        return False

    action = payload.get("type")
    try:
        if action in ("click", "move", "dblclick", "rightclick"):
            x = int(float(payload.get("x", 0)) * width)
            y = int(float(payload.get("y", 0)) * height)
            _pyautogui.moveTo(x, y)
            if action == "click":
                _pyautogui.click()
            elif action == "dblclick":
                _pyautogui.doubleClick()
            elif action == "rightclick":
                _pyautogui.click(button="right")
        elif action == "type":
            _pyautogui.typewrite(str(payload.get("text", "")), interval=0.01)
        elif action == "key":
            _pyautogui.press(str(payload.get("key", "")))
        elif action == "scroll":
            _pyautogui.scroll(int(payload.get("amount", 0)))
        else:
            return False
        return True
    except Exception as exc:
        log("styrfel: %s" % exc)
        return False


# =====================================================================
#  LAN-viewer (samma utseende som molnvyn)
# =====================================================================

VIEWER_HTML = """<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#08090b">
<title>StagEye — __ROOM_LABEL__</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0; height: 100%; background: #08090b; color: #e7e9ee;
    font-family: ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
    overscroll-behavior: none;
  }
  body { display: flex; flex-direction: column; }

  header {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 16px; border-bottom: 1px solid #1c1f26; background: #0b0d11;
    padding-top: calc(12px + env(safe-area-inset-top));
  }
  .brand { font-weight: 700; letter-spacing: .14em; font-size: 12px; color: #6b7280; }
  .room { font-weight: 600; font-size: 15px; }
  .spacer { flex: 1; }

  .pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 5px 11px; border-radius: 999px; font-size: 11px;
    font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
    border: 1px solid #1c1f26; background: #101317; color: #9aa3b2;
  }
  .dot { width: 7px; height: 7px; border-radius: 999px; background: #6b7280; }
  .pill.live { color: #34d399; border-color: #14532d; background: #0c1a14; }
  .pill.live .dot { background: #34d399; animation: pulse 2s ease-in-out infinite; }
  .pill.stale { color: #f87171; border-color: #4c1d1d; background: #1a0e0e; }
  .pill.stale .dot { background: #f87171; }
  @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }

  main { flex: 1; display: flex; align-items: center; justify-content: center; padding: 14px; min-height: 0; }
  .frame {
    position: relative; max-width: 100%; max-height: 100%;
    border: 1px solid #1c1f26; border-radius: 12px; overflow: hidden;
    background: #000; box-shadow: 0 18px 50px rgba(0,0,0,.6);
  }
  #screen { display: block; max-width: 100%; max-height: 78vh; width: auto; height: auto; }
  .frame.control { cursor: crosshair; border-color: #2563eb; }

  footer {
    display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
    padding: 10px 16px; border-top: 1px solid #1c1f26; background: #0b0d11;
    font-size: 11px; color: #6b7280;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    padding-bottom: calc(10px + env(safe-area-inset-bottom));
  }
  footer b { color: #9aa3b2; font-weight: 600; }
  .btn {
    margin-left: auto; padding: 6px 12px; border-radius: 8px; cursor: pointer;
    border: 1px solid #1c1f26; background: #101317; color: #9aa3b2;
    font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  }
  .btn.on { color: #93c5fd; border-color: #1e3a8a; background: #0c1220; }
</style>
</head>
<body>
  <header>
    <span class="brand">STAGEYE</span>
    <span class="room">__ROOM_LABEL__</span>
    <span class="spacer"></span>
    <span class="pill" id="status"><span class="dot"></span><span id="statusText">Ansluter</span></span>
  </header>

  <main>
    <div class="frame" id="frame">
      <img id="screen" alt="FOH-skarm">
    </div>
  </main>

  <footer>
    <span><b id="fps">0.0</b> fps</span>
    <span><b id="age">–</b> ms</span>
    <span><b id="res">–</b></span>
    <span><b>LAN</b></span>
    <button class="btn" id="controlBtn">Styrning av</button>
  </footer>

<script>
  var img = document.getElementById('screen');
  var frame = document.getElementById('frame');
  var statusEl = document.getElementById('status');
  var statusText = document.getElementById('statusText');
  var controlBtn = document.getElementById('controlBtn');
  var controlOn = false;
  var lastSeq = -1, frames = 0, fpsWindow = Date.now();

  function loadFrame() {
    var next = new Image();
    next.onload = function () {
      img.src = next.src;
      frames++;
      setTimeout(loadFrame, 250);
    };
    next.onerror = function () {
      setStatus('stale', 'Fransluten');
      setTimeout(loadFrame, 1500);
    };
    next.src = '/latest.jpg?t=' + Date.now();
  }

  function setStatus(kind, text) {
    statusEl.className = 'pill' + (kind ? ' ' + kind : '');
    statusText.textContent = text;
  }

  function poll() {
    fetch('/status', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (s) {
        var age = Math.round(s.frame_age * 1000);
        document.getElementById('age').textContent = age;
        document.getElementById('res').textContent = s.width + '×' + s.height;
        setStatus(age < 4000 ? 'live' : 'stale', age < 4000 ? 'Live' : 'Ingen bild');
        if (!s.control) { controlBtn.style.display = 'none'; }
      })
      .catch(function () { setStatus('stale', 'Fransluten'); });
  }

  setInterval(poll, 2000);
  setInterval(function () {
    var now = Date.now();
    document.getElementById('fps').textContent = (frames / ((now - fpsWindow) / 1000)).toFixed(1);
    frames = 0; fpsWindow = now;
  }, 3000);

  controlBtn.onclick = function () {
    controlOn = !controlOn;
    controlBtn.classList.toggle('on', controlOn);
    frame.classList.toggle('control', controlOn);
    controlBtn.textContent = controlOn ? 'Styrning pa' : 'Styrning av';
  };

  img.onclick = function (event) {
    if (!controlOn) return;
    var box = img.getBoundingClientRect();
    fetch('/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'click',
        x: (event.clientX - box.left) / box.width,
        y: (event.clientY - box.top) / box.height
      })
    });
  };

  loadFrame();
  poll();
</script>
</body>
</html>
"""


class StagEyeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # tyst — pythonw har ingen konsol

    def _send(self, code, content_type, body, extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ("/", "/index.html"):
            html = VIEWER_HTML.replace("__ROOM_LABEL__", ROOM_LABEL)
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
            return

        if path == "/latest.jpg":
            with _state_lock:
                jpeg = _latest_jpeg
            if jpeg is None:
                self._send(503, "text/plain", b"ingen bild an")
            else:
                self._send(200, "image/jpeg", jpeg)
            return

        if path == "/status":
            with _state_lock:
                width, height = _screen_size
                age = 0.0 if _latest_jpeg is None else max(0.0, time.time() - _last_frame_time())
                payload = {
                    "room": ROOM,
                    "label": ROOM_LABEL,
                    "width": width,
                    "height": height,
                    "frame_age": age,
                    "seq": _latest_seq,
                    "uptime": time.time() - _started_at,
                    "cloud_ok": _last_upload_ok,
                    "control": _pyautogui is not None,
                }
            self._send(200, "application/json", json.dumps(payload).encode("utf-8"))
            return

        self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if self.path.split("?")[0] != "/control":
            self._send(404, "text/plain", b"not found")
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = {}

        ok = handle_control(payload)
        self._send(200 if ok else 400, "application/json",
                   json.dumps({"ok": ok}).encode("utf-8"))


_frame_stamp = [0.0]


def _last_frame_time():
    return _frame_stamp[0]


def _stamp_watcher():
    """Uppdaterar tidsstampeln varje gang en ny bild dyker upp."""
    last = -1
    while True:
        with _state_lock:
            seq = _latest_seq
        if seq != last:
            last = seq
            _frame_stamp[0] = time.time()
        time.sleep(0.1)


# =====================================================================
#  Start
# =====================================================================

def main():
    log("StagEye startar — rum=%s port=%s" % (ROOM, LOCAL_PORT))

    threading.Thread(target=capture_loop, daemon=True).start()
    threading.Thread(target=_stamp_watcher, daemon=True).start()
    threading.Thread(target=upload_loop, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", LOCAL_PORT), StagEyeHandler)
    log("LAN-viewer: http://%s:%s/" % (local_ip(), LOCAL_PORT))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        log("StagEye avslutad")


if __name__ == "__main__":
    main()
