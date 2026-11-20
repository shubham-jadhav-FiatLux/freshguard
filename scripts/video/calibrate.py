"""Finds, per clip, the offset between logged event times and the video timeline.

Playwright's video does not start exactly when the page opens, so we match the logged key/click
times against the frames where the typed text visibly changes. Writes clips/offsets.json.
"""
import json, pathlib, subprocess
import numpy as np

S = pathlib.Path(__file__).parent
CLIPS = S / "clips"
# crop (w:h:x:y in the 1280x720 video) where each clip's typing shows up
CROPS = {"ui_ask": "500:30:235:395",
         "term1": "1100:60:80:70", "term2": "1100:60:80:70"}


def changes(name, crop):
    w, h = map(int, crop.split(":")[:2])
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(CLIPS / f"{name}.webm"), "-t", "20",
                          "-vf", f"crop={crop},format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int32)
    d = np.abs(np.diff(f, axis=0)).sum(axis=(1, 2))
    return np.array([(i + 1) / 25 for i in np.nonzero(d > 800)[0]])


def best_offset(ev, ch):
    best = (-1, 0.0)
    for off in np.arange(-0.5, 2.5, 0.01):
        # a key shows up on the first frame at or after it (frames are 40 ms apart)
        hits = sum(np.any((ch >= t + off - 0.005) & (ch <= t + off + 0.085)) for t in ev)
        if hits > best[0]:
            best = (hits, round(float(off), 2))
    return best


out = {}
for name, crop in CROPS.items():
    e = json.loads((CLIPS / f"{name}.events.json").read_text())
    ev = [t - e["t_open"] for t, k in e["events"] if k in ("key", "space")]
    hits, off = best_offset(ev, changes(name, crop))
    out[name] = off
    print(f"{name}: offset {off:+.2f}s ({hits}/{len(ev)} events matched)")
# The paste clip has one visible change and a blinking caret; it is the same page as ui_ask, so share its offset.
out["ui_paste"] = out["ui_ask"]
(CLIPS / "offsets.json").write_text(json.dumps(out))
