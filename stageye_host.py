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
DEFAULT_MONITOR = 2                  # 1 = primar skarm, 2 = andra skarmen, 0 = alla

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
_screen_origin = (0, 0)      # (left, top) for vald skarm — behovs for musstyrning
_monitor_index = DEFAULT_MONITOR
_monitor_count = 0           # antal fysiska skarmar
_last_upload_ok = None       # None = inte forsokt an, True/False efter forsta forsoket
_started_at = time.time()
_frame_stamp = 0.0           # nar senaste bilden togs


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
    global _latest_jpeg, _latest_seq, _screen_size, _screen_origin
    global _monitor_count, _frame_stamp, _monitor_index

    with mss.mss() as sct:
        with _state_lock:
            _monitor_count = max(0, len(sct.monitors) - 1)
            if _monitor_index >= len(sct.monitors):
                _monitor_index = 1
        log("hittade %s skarm(ar)" % _monitor_count)

        while True:
            start = time.time()
            try:
                with _state_lock:
                    index = _monitor_index
                if index >= len(sct.monitors):
                    index = 1

                monitor = sct.monitors[index]
                shot = sct.grab(monitor)
                image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=LOCAL_QUALITY)

                with _state_lock:
                    _latest_jpeg = buffer.getvalue()
                    _latest_seq += 1
                    _screen_size = image.size
                    _screen_origin = (monitor["left"], monitor["top"])
                    _frame_stamp = time.time()
            except Exception as exc:
                log("capture-fel: %s" % exc)
                time.sleep(2)

            elapsed = time.time() - start
            time.sleep(max(0.0, LOCAL_INTERVAL - elapsed))


# =====================================================================
#  Trad 2 — uppladdning till Supabase
# =====================================================================

def upload_loop():
    global _last_upload_ok

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
            image = Image.open(io.BytesIO(jpeg))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=CLOUD_QUALITY)

            response = requests.put(url, headers=headers, data=buffer.getvalue(), timeout=10)
            ok = response.status_code in (200, 201)

            with _state_lock:
                if _last_upload_ok is not True and ok:
                    log("uppladdning fungerar")
                _last_upload_ok = ok

            if not ok:
                log("uppladdning nekad: HTTP %s %s" % (response.status_code, response.text[:200]))
        except Exception as exc:
            with _state_lock:
                if _last_upload_ok is not False:
                    log("uppladdning misslyckas (LAN-laget paverkas inte): %s" % exc)
                _last_upload_ok = False


# =====================================================================
#  Fjarrstyrning
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
        left, top = _screen_origin

    action = payload.get("type")

    try:
        if action in ("click", "move", "dblclick", "rightclick"):
            if width == 0 or height == 0:
                return False
            x = left + int(float(payload.get("x", 0)) * width)
            y = top + int(float(payload.get("y", 0)) * height)
            _pyautogui.moveTo(x, y)
            if action == "click":
                _pyautogui.click()
            elif action == "dblclick":
                _pyautogui.doubleClick()
            elif action == "rightclick":
                _pyautogui.click(button="right")
        elif action == "drag":
            if width == 0 or height == 0:
                return False
            x1 = left + int(float(payload.get("x1", 0)) * width)
            y1 = top + int(float(payload.get("y1", 0)) * height)
            x2 = left + int(float(payload.get("x2", 0)) * width)
            y2 = top + int(float(payload.get("y2", 0)) * height)
            _pyautogui.moveTo(x1, y1)
            _pyautogui.mouseDown()
            _pyautogui.moveTo(x2, y2, duration=0.25)
            _pyautogui.mouseUp()
        elif action == "type":
            _pyautogui.typewrite(str(payload.get("text", "")), interval=0.01)
        elif action == "key":
            _pyautogui.press(str(payload.get("key", "")))
        elif action == "hotkey":
            keys = payload.get("keys", [])
            if not keys:
                return False
            _pyautogui.hotkey(*[str(k) for k in keys])
        elif action == "scroll":
            _pyautogui.scroll(int(payload.get("amount", 0)))
        else:
            return False
        return True
    except Exception as exc:
        log("styrfel: %s" % exc)
        return False


# =====================================================================
#  LAN-viewer
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
  #screen {
    display: block; max-width: 100%; max-height: 72vh; width: auto; height: auto;
    -webkit-touch-callout: none;
    -webkit-user-select: none;
    user-select: none;
    -webkit-user-drag: none;
    pointer-events: auto;
  }
  .frame.control { cursor: crosshair; border-color: #2563eb; }
  .frame.control #screen { touch-action: none; }

  footer {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    padding: 10px 16px; border-top: 1px solid #1c1f26; background: #0b0d11;
    font-size: 11px; color: #6b7280;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    padding-bottom: calc(10px + env(safe-area-inset-bottom));
  }
  footer b { color: #9aa3b2; font-weight: 600; }
  .grow { flex: 1; }
  .stat { margin-right: 6px; }

  .btn {
    padding: 6px 12px; border-radius: 8px; cursor: pointer;
    border: 1px solid #1c1f26; background: #101317; color: #9aa3b2;
    font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
  }
  .btn.on { color: #93c5fd; border-color: #1e3a8a; background: #0c1220; }
  .btn:disabled { opacity: .4; cursor: default; }

  .keys {
    display: none; gap: 8px; flex-wrap: wrap; align-items: center;
    padding: 10px 16px; border-top: 1px solid #1c1f26; background: #0b0d11;
  }
  .keys.show { display: flex; }
  .keys input {
    flex: 1; min-width: 120px; padding: 7px 10px; border-radius: 8px;
    border: 1px solid #1c1f26; background: #101317; color: #e7e9ee; font-size: 13px;
  }
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

  <div class="keys" id="keys">
    <button class="btn" id="dblBtn">Dubbelklick</button>
    <button class="btn" id="rightBtn">Högerklick</button>
    <input id="textInput" placeholder="Skriv text…" autocomplete="off">
    <button class="btn" id="sendBtn">Skicka</button>
    <button class="btn" id="enterBtn">Enter</button>
    <button class="btn" id="escBtn">Esc</button>
    <button class="btn" id="winBtn">Win</button>
  </div>

  <footer>
    <span class="stat"><b id="fps">0.0</b> fps</span>
    <span class="stat"><b id="age">–</b> ms</span>
    <span class="stat"><b id="res">–</b></span>
    <span class="grow"></span>
    <span id="screens"></span>
    <button class="btn" id="controlBtn">Styrning av</button>
  </footer>

<script>
  var img = document.getElementById('screen');
  var frame = document.getElementById('frame');
  var statusEl = document.getElementById('status');
  var statusText = document.getElementById('statusText');
  var controlBtn = document.getElementById('controlBtn');
  var screensEl = document.getElementById('screens');
  var keysEl = document.getElementById('keys');
  var textInput = document.getElementById('textInput');

  var controlOn = false;
  var controlAvailable = false;
  var nextClickIsDouble = false;
  var nextClickIsRight = false;
  var frames = 0, fpsWindow = Date.now();

  function post(path, body) {
    return fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  }

  function loadFrame() {
    var next = new Image();
    next.onload = function () {
      img.src = next.src;
      frames++;
      setTimeout(loadFrame, 250);
    };
    next.onerror = function () {
      setStatus('stale', 'Ej ansluten');
      setTimeout(loadFrame, 1500);
    };
    next.src = '/latest.jpg?t=' + Date.now();
  }

  function setStatus(kind, text) {
    statusEl.className = 'pill' + (kind ? ' ' + kind : '');
    statusText.textContent = text;
  }

  function renderScreens(count, current) {
    if (screensEl.dataset.count === String(count) &&
        screensEl.dataset.current === String(current)) return;
    screensEl.dataset.count = count;
    screensEl.dataset.current = current;
    screensEl.innerHTML = '';
    if (count < 2) return;

    for (var i = 1; i <= count; i++) {
      (function (index) {
        var button = document.createElement('button');
        button.className = 'btn' + (index === current ? ' on' : '');
        button.style.marginRight = '6px';
        button.textContent = 'Skärm ' + index;
        button.onclick = function () {
          post('/monitor', { index: index }).then(poll);
        };
        screensEl.appendChild(button);
      })(i);
    }
  }

  function poll() {
    fetch('/status', { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (s) {
        var age = Math.round(s.frame_age * 1000);
        document.getElementById('age').textContent = age;
        document.getElementById('res').textContent = s.width + '×' + s.height;
        setStatus(age < 4000 ? 'live' : 'stale', age < 4000 ? 'Live' : 'Ingen bild');
        renderScreens(s.monitors, s.monitor);
        controlAvailable = s.control;
        controlBtn.style.display = s.control ? '' : 'none';
      })
      .catch(function () { setStatus('stale', 'Ej ansluten'); });
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
    keysEl.classList.toggle('show', controlOn);
    controlBtn.textContent = controlOn ? 'Styrning på' : 'Styrning av';
  };

  function sendTap(clientX, clientY) {
    if (!controlOn) return;
    var box = img.getBoundingClientRect();
    var type = nextClickIsDouble ? 'dblclick' : (nextClickIsRight ? 'rightclick' : 'click');
    nextClickIsDouble = false;
    nextClickIsRight = false;
    document.getElementById('dblBtn').classList.remove('on');
    document.getElementById('rightBtn').classList.remove('on');
    post('/control', {
      type: type,
      x: (clientX - box.left) / box.width,
      y: (clientY - box.top) / box.height
    });
  }

  img.addEventListener('click', function (event) {
    sendTap(event.clientX, event.clientY);
  });

  var touchStart = null;

  img.addEventListener('touchstart', function (event) {
    if (!controlOn) return;
    var touch = event.changedTouches[0];
    if (!touch) return;
    event.preventDefault();
    touchStart = { x: touch.clientX, y: touch.clientY };
  }, { passive: false });

  img.addEventListener('touchmove', function (event) {
    if (!controlOn || !touchStart) return;
    event.preventDefault();
  }, { passive: false });

  img.addEventListener('touchcancel', function () {
    touchStart = null;
  }, { passive: true });

  img.addEventListener('contextmenu', function (event) {
    if (controlOn) event.preventDefault();
  });

  img.addEventListener('touchend', function (event) {
    if (!controlOn) return;
    var touch = event.changedTouches[0];
    if (!touch) return;
    event.preventDefault();

    var start = touchStart;
    touchStart = null;

    if (start) {
      var moved = Math.abs(touch.clientX - start.x) + Math.abs(touch.clientY - start.y);
      if (moved > 20) {
        var box = img.getBoundingClientRect();
        post('/control', {
          type: 'drag',
          x1: (start.x - box.left) / box.width,
          y1: (start.y - box.top) / box.height,
          x2: (touch.clientX - box.left) / box.width,
          y2: (touch.clientY - box.top) / box.height
        });
        return;
      }
    }

    sendTap(touch.clientX, touch.clientY);
  }, { passive: false });

  document.getElementById('dblBtn').onclick = function () {
    nextClickIsDouble = !nextClickIsDouble;
    nextClickIsRight = false;
    this.classList.toggle('on', nextClickIsDouble);
    document.getElementById('rightBtn').classList.remove('on');
  };

  document.getElementById('rightBtn').onclick = function () {
    nextClickIsRight = !nextClickIsRight;
    nextClickIsDouble = false;
    this.classList.toggle('on', nextClickIsRight);
    document.getElementById('dblBtn').classList.remove('on');
  };

  document.getElementById('sendBtn').onclick = function () {
    if (!textInput.value) return;
    post('/control', { type: 'type', text: textInput.value });
    textInput.value = '';
  };

  textInput.addEventListener('keydown', function (event) {
    if (event.key === 'Enter') { document.getElementById('sendBtn').click(); }
  });

  document.getElementById('enterBtn').onclick = function () {
    post('/control', { type: 'key', key: 'enter' });
  };
  document.getElementById('escBtn').onclick = function () {
    post('/control', { type: 'key', key: 'esc' });
  };
  document.getElementById('winBtn').onclick = function () {
    post('/control', { type: 'key', key: 'win' });
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

    def _send(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

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
                age = 0.0 if _frame_stamp == 0.0 else max(0.0, time.time() - _frame_stamp)
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
                    "monitor": _monitor_index,
                    "monitors": _monitor_count,
                }
            self._send(200, "application/json", json.dumps(payload).encode("utf-8"))
            return

        self._send(404, "text/plain", b"not found")

    def do_POST(self):
        global _monitor_index
        path = self.path.split("?")[0]

        if path == "/control":
            ok = handle_control(self._read_json())
            self._send(200 if ok else 400, "application/json",
                       json.dumps({"ok": ok}).encode("utf-8"))
            return

        if path == "/monitor":
            payload = self._read_json()
            try:
                index = int(payload.get("index", DEFAULT_MONITOR))
            except Exception:
                index = DEFAULT_MONITOR

            with _state_lock:
                count = _monitor_count
                if 0 <= index <= count:
                    _monitor_index = index
                    ok = True
                else:
                    ok = False

            if ok:
                log("bytte till skarm %s" % index)
            self._send(200 if ok else 400, "application/json",
                       json.dumps({"ok": ok, "monitor": index}).encode("utf-8"))
            return

        self._send(404, "text/plain", b"not found")


# =====================================================================
#  Start
# =====================================================================

def main():
    log("StagEye startar — rum=%s port=%s" % (ROOM, LOCAL_PORT))

    threading.Thread(target=capture_loop, daemon=True).start()
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
