"""
Valorant minimap "last enemy sighting" recorder.

Watches a 448x448 region in the top-left corner of a chosen window for two
specific colors (enemy dots on the minimap). While either color is present
it keeps grabbing frames. The instant the color disappears, it publishes the
LAST frame that still had the color on it to a tiny local web server, so you
can check your phone after a fight to see where the enemy last showed up.

Setup:
    pip install mss numpy Pillow pygetwind"""
Valorant minimap "last enemy sighting" recorder.

Watches a 448x448 region in the top-left corner of a chosen window for two
specific colors (enemy dots on the minimap). While either color is present
it keeps grabbing frames. The instant the color disappears, it publishes the
LAST frame that still had the color on it to a tiny local web server, so you
can check your phone after a fight to see where the enemy last showed up.

Setup:
    pip install mss numpy Pillow pygetwindow flask pywin32

Run:
    python monitor.py

Then on your phone (same WiFi), open:
    http://<your-pc-local-ip>:5000
Find your PC's local IP with `ipconfig` (look for IPv4 Address under your
WiFi adapter). Make sure Windows Firewall allows Python / port 5000 on
private networks.
"""

import time
import threading
from pathlib import Path

import numpy as np
import mss
from PIL import Image
import pygetwindow as gw
from flask import Flask, Response, jsonify, render_template_string

# ---------------- CONFIG ----------------
WINDOW_TITLE = "VALORANT"              # partial/exact title of the window to capture
CAPTURE_SIZE = 280                     # width/height of the capture box (px) - {decrease the area for more accuracy}
OFFSET_X = 0                           # shift capture box right from window's left edge
OFFSET_Y = 0                           # shift capture box down from window's top edge
TARGET_COLORS = ["b0292c"]             # hex color to watch for (enemy dot/arrow)
COLOR_TOLERANCE = 28                   # per-channel tolerance, 0-255 (raise if it misses, lower if false positives)
                                        # NOTE: don't set this anywhere near 255 - if every channel
                                        # can differ by up to 255, EVERY pixel matches trivially, and
                                        # the script will think the color never disappears.
POLL_INTERVAL = 0.15                   # seconds between capture checks (~6-7 fps)
JPEG_QUALITY = 85
OUTPUT_DIR = Path("snapshots")
DISPLAY_FILE = OUTPUT_DIR / "display.jpg"
HOST = "0.0.0.0"
PORT = 5000
# -----------------------------------------

OUTPUT_DIR.mkdir(exist_ok=True)


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


TARGET_RGB = [hex_to_rgb(c) for c in TARGET_COLORS]


def get_capture_region():
    """Locate the target window and return the capture region dict for mss."""
    matches = [w for w in gw.getAllWindows() if WINDOW_TITLE.lower() in w.title.lower()]
    if not matches:
        raise RuntimeError(f"No window found with title containing '{WINDOW_TITLE}'")
    win = matches[0]
    if win.isMinimized:
        raise RuntimeError(f"Window '{win.title}' is minimized")
    return {
        "left": win.left + OFFSET_X,
        "top": win.top + OFFSET_Y,
        "width": CAPTURE_SIZE,
        "height": CAPTURE_SIZE,
    }


def contains_target_color(rgb_arr: np.ndarray) -> bool:
    """rgb_arr: HxWx3 uint8 array. True if any pixel is close to a target color."""
    for rgb in TARGET_RGB:
        diff = np.abs(rgb_arr.astype(np.int16) - np.array(rgb, dtype=np.int16))
        if np.all(diff <= COLOR_TOLERANCE, axis=-1).any():
            return True
    return False


def save_jpeg(rgb_arr: np.ndarray, path: Path):
    Image.fromarray(rgb_arr, "RGB").save(path, "JPEG", quality=JPEG_QUALITY)


def capture_loop():
    color_active = False
    last_active_frame = None
    warned_missing = False

    with mss.mss() as sct:
        while True:
            try:
                region = get_capture_region()
                shot = sct.grab(region)
                # mss gives BGRA; drop alpha and flip to RGB
                frame = np.array(shot)[:, :, :3][:, :, ::-1]
                warned_missing = False

                if contains_target_color(frame):
                    color_active = True
                    last_active_frame = frame
                elif color_active:
                    # color just disappeared -> publish the last frame that had it
                    if last_active_frame is not None:
                        save_jpeg(last_active_frame, DISPLAY_FILE)
                    color_active = False

            except RuntimeError as e:
                if not warned_missing:
                    print(f"[warn] {e}")
                    warned_missing = True
            except Exception as e:
                print(f"[error] {e}")

            time.sleep(POLL_INTERVAL)


app = Flask(__name__)

PAGE = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Last enemy sighting</title>
  <style>
    body { background:#111; margin:0; display:flex; flex-direction:column;
           justify-content:center; align-items:center; height:100vh;
           font-family:sans-serif; }
    img { max-width:100%; max-height:88vh; image-rendering:pixelated; }
    #age { margin-top:10px; font-size:22px; font-weight:bold; letter-spacing:0.5px; }
    .fresh { color:#4caf50; }    /* < 5s: solid, trust it */
    .recent { color:#ffb300; }   /* < 15s: probably still relevant */
    .stale { color:#e53935; }    /* 15s+: old news, treat with caution */
    .none { color:#888; }
  </style>
</head>
<body>
  <img id="shot" src="/image" onerror="this.style.display='none'">
  <div id="age" class="none">waiting for first sighting...</div>
  <script>
    function formatAge(s) {
      if (s === null) return "no sighting yet";
      if (s < 1) return "just now";
      if (s < 60) return Math.floor(s) + " sec ago";
      return Math.floor(s / 60) + " min " + Math.floor(s % 60) + " sec ago";
    }
    function classFor(s) {
      if (s === null) return "none";
      if (s < 5) return "fresh";
      if (s < 15) return "recent";
      return "stale";
    }
    async function refresh() {
      const img = document.getElementById('shot');
      const ageEl = document.getElementById('age');
      img.src = '/image?t=' + Date.now();
      img.style.display = '';
      try {
        const res = await fetch('/age?t=' + Date.now());
        const data = await res.json();
        ageEl.textContent = formatAge(data.age_seconds);
        ageEl.className = classFor(data.age_seconds);
      } catch (e) {
        // server hiccup, keep showing last known age rather than erroring out
      }
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/image")
def image():
    if not DISPLAY_FILE.exists():
        return "No snapshot yet", 404
    return Response(DISPLAY_FILE.read_bytes(), mimetype="image/jpeg")


@app.route("/age")
def age():
    if not DISPLAY_FILE.exists():
        return jsonify({"age_seconds": None})
    # file's own mtime = the moment save_jpeg() wrote it, no shared state needed
    age_seconds = time.time() - DISPLAY_FILE.stat().st_mtime
    return jsonify({"age_seconds": round(age_seconds, 1)})


if __name__ == "__main__":
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    print(f"Server running. On your phone (same WiFi) open http://<your-pc-local-ip>:{PORT}")
    app.run(host=HOST, port=PORT)
ow flask pywin32

Run:
    python monitor.py

Then on your phone (same WiFi), open:
    http://<your-pc-local-ip>:5000
Find your PC's local IP with `ipconfig` (look for IPv4 Address under your
WiFi adapter). Make sure Windows Firewall allows Python / port 5000 on
private networks.
"""

import time
import threading
from pathlib import Path

import numpy as np
import mss
from PIL import Image
import pygetwindow as gw
from flask import Flask, Response, render_template_string

# ---------------- CONFIG ----------------
WINDOW_TITLE = "VALORANT"              # partial/exact title of the window to capture
CAPTURE_SIZE = 320                     # width/height of the capture box (px)
OFFSET_X = 0                           # shift capture box right from window's left edge
OFFSET_Y = 0                           # shift capture box down from window's top edge
TARGET_COLORS = ["b0292c"]             # hex colors to watch for (enemy dots)
COLOR_TOLERANCE = 28                   # per-channel tolerance, 0-255 (raise if it misses, lower if false positives)
POLL_INTERVAL = 0.15                   # seconds between capture checks (~6-7 fps)
JPEG_QUALITY = 85
OUTPUT_DIR = Path("snapshots")
DISPLAY_FILE = OUTPUT_DIR / "display.jpg"
HOST = "0.0.0.0"
PORT = 5000
# -----------------------------------------

OUTPUT_DIR.mkdir(exist_ok=True)


def hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


TARGET_RGB = [hex_to_rgb(c) for c in TARGET_COLORS]


def get_capture_region():
    """Locate the target window and return the capture region dict for mss."""
    matches = [w for w in gw.getAllWindows() if WINDOW_TITLE.lower() in w.title.lower()]
    if not matches:
        raise RuntimeError(f"No window found with title containing '{WINDOW_TITLE}'")
    win = matches[0]
    if win.isMinimized:
        raise RuntimeError(f"Window '{win.title}' is minimized")
    return {
        "left": win.left + OFFSET_X,
        "top": win.top + OFFSET_Y,
        "width": CAPTURE_SIZE,
        "height": CAPTURE_SIZE,
    }


def contains_target_color(rgb_arr: np.ndarray) -> bool:
    """rgb_arr: HxWx3 uint8 array. True if any pixel is close to a target color."""
    for rgb in TARGET_RGB:
        diff = np.abs(rgb_arr.astype(np.int16) - np.array(rgb, dtype=np.int16))
        if np.all(diff <= COLOR_TOLERANCE, axis=-1).any():
            return True
    return False


def save_jpeg(rgb_arr: np.ndarray, path: Path):
    Image.fromarray(rgb_arr, "RGB").save(path, "JPEG", quality=JPEG_QUALITY)


def capture_loop():
    color_active = False
    last_active_frame = None
    warned_missing = False

    with mss.mss() as sct:
        while True:
            try:
                region = get_capture_region()
                shot = sct.grab(region)
                # mss gives BGRA; drop alpha and flip to RGB
                frame = np.array(shot)[:, :, :3][:, :, ::-1]
                warned_missing = False

                if contains_target_color(frame):
                    color_active = True
                    last_active_frame = frame
                elif color_active:
                    # color just disappeared -> publish the last frame that had it
                    if last_active_frame is not None:
                        save_jpeg(last_active_frame, DISPLAY_FILE)
                    color_active = False

            except RuntimeError as e:
                if not warned_missing:
                    print(f"[warn] {e}")
                    warned_missing = True
            except Exception as e:
                print(f"[error] {e}")

            time.sleep(POLL_INTERVAL)


app = Flask(__name__)

PAGE = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Last enemy sighting</title>
  <style>
    body { background:#111; margin:0; display:flex; justify-content:center;
           align-items:center; height:100vh; }
    img { max-width:100%; max-height:100vh; image-rendering:pixelated; }
    .empty { color:#888; font-family:sans-serif; }
  </style>
</head>
<body>
  <img id="shot" src="/image" onerror="this.style.display='none'">
  <script>
    setInterval(() => {
      const img = document.getElementById('shot');
      img.src = '/image?t=' + Date.now();
      img.style.display = '';
    }, 1000);
  </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/image")
def image():
    if not DISPLAY_FILE.exists():
        return "No snapshot yet", 404
    return Response(DISPLAY_FILE.read_bytes(), mimetype="image/jpeg")


if __name__ == "__main__":
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    print(f"Server running. On your phone (same WiFi) open http://<your-pc-local-ip>:{PORT}")
    app.run(host=HOST, port=PORT)
