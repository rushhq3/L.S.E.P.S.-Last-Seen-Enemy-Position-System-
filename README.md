# L.S.E.P.S. — Last Seen Enemy Position System™

*(Because your teammates won't give comms)*

Watches a 448×448 box in the top-left corner of your game window — right
where the minimap lives. The instant an enemy indicator color shows up, it
starts grabbing frames. The instant that color disappears again, it publishes
the **last frame that still had it** to a tiny local web server — so after
the gunfight's over, you can glance at your phone and see exactly where they
last were. No comms required.

> Built for Valorant's minimap, but the color-watching logic doesn't care
> what game it's pointed at — if it's got a colored blip on a fixed HUD
> element, this'll track it.

---

## Table of Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Setup](#setup)
- [Configure](#configure)
- [Running it](#running-it)
- [Viewing it on your phone](#viewing-it-on-your-phone)
- [Firewall](#firewall)
- [Tuning](#tuning)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## How it works

1. `mss` grabs a 448×448 region from the top-left of your game window,
   several times a second.
2. Every frame is checked pixel-by-pixel for a match against a target hex
   color (with some tolerance, since anti-aliasing means exact matches
   basically never happen).
3. While the color is present, the frame is held in memory as "last known
   good" — nothing is published yet.
4. The moment the color **stops** appearing, that last held frame gets
   saved and served up via Flask.
5. Your phone (same WiFi) polls that image once a second, so it's always
   showing the most recent sighting — frozen there until the next one.

## Requirements

- Windows (uses `pygetwindow` + `pywin32` to locate the game window)
- Python 3.9+
- Your PC and phone on the **same WiFi network**

## Setup

```
pip install -r requirements.txt
```

## Configure

Open `monitor.py` and check the config block near the top:

| Setting | What it does |
|---|---|
| `WINDOW_TITLE` | Partial/exact title of the window to capture. Valorant's is usually just `"VALORANT"` — confirm in Task Manager if unsure. |
| `OFFSET_X` / `OFFSET_Y` | Nudge the capture box if the minimap isn't flush against the window's top-left pixel. |
| `TARGET_COLORS` | Hex color(s) to watch for. |
| `COLOR_TOLERANCE` | Per-channel tolerance (0–255). See [Tuning](#tuning) below — **do not set this to 255 or anything close to it.** |
| `POLL_INTERVAL` | Seconds between checks. Lower = faster detection, more CPU. |

## Running it

```
python monitor.py
```

Leave it running in the background while you play. It grabs pixels straight
from the screen buffer, so the game window doesn't need focus — tab over to
Discord, doesn't matter.

## Viewing it on your phone

1. Same WiFi network as your PC — non-negotiable.
2. On your PC: `ipconfig` in PowerShell → find the IPv4 address under your
   WiFi adapter (`192.168.x.x`).
3. On your phone's browser: `http://192.168.x.x:5000`
4. Page auto-refreshes every second and always shows the last confirmed
   sighting.

## Firewall

Windows will likely prompt to allow Python through the firewall the first
run — allow it for **Private networks**. If your phone can't load the page,
check Windows Defender Firewall → Allowed apps and make sure Python (or
port 5000) is allowed there.

## Tuning

- **`POLL_INTERVAL`** (default `0.15`, ~6–7 checks/sec) trades responsiveness
  for CPU usage. Lower it for faster detection, raise it if it's chewing
  through CPU mid-match.
- **Display scaling**: if Windows Display Settings has scaling above 100%,
  `pygetwindow` coordinates can be off by that factor, and your capture box
  will look shifted. Either set scaling to 100% or compensate in
  `OFFSET_X` / `OFFSET_Y`.

### A word on `COLOR_TOLERANCE`

This is the setting most likely to bite you, so here's the honest version:

- **Too low** → misses the real color (anti-aliased edges never quite hit
  the exact hex value).
- **Too high** → false-positives on unrelated background colors that happen
  to be "hex-adjacent," *and* — this is the sneaky one — if it's high enough
  that basically every pixel qualifies, the tool will think the color is
  **always** present and never register the "it disappeared" moment. Since
  publishing only happens on disappearance, that means the display just...
  stops updating. Looks like a bug. Isn't. Learned this one the hard way.
- **The sweet spot** is usually a fairly narrow band (think ~25–30 for the
  default enemy-red target) — comfortably enough to catch the real dot,
  tight enough that random wall textures don't sneak in. Test against a
  screenshot with the color present and one without, and pick the tolerance
  where you get zero matches on the "without" image and several matches on
  the "with" image.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Nothing ever shows up | `WINDOW_TITLE` doesn't match your game window, or window is minimized |
| Capture box is in the wrong spot | Check `OFFSET_X`/`OFFSET_Y`, and Windows display scaling |
| Image never updates after the first time | `COLOR_TOLERANCE` too high — see above |
| Detecting things that aren't the enemy dot | `COLOR_TOLERANCE` too high, or your target hex isn't as exclusive to the marker as you think — sample real screenshots before trusting a color |
| Can't load the page on phone | Different WiFi network, or firewall blocking the port |

## Note

Built with the help of Claude (Anthropic).

## Contributing

If you'd like to improve this, feel free to — just let me know what you
changed.

## License

MIT. Do what you want with it.
