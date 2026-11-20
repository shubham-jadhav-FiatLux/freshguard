"""Synthesises the demo's soundtrack: a calm instrumental bed plus keyboard/mouse clicks on every
recorded key press. Everything is generated here (no samples), so there are no licensing questions.

Usage: soundtrack.py <timeline.json> <total_seconds> <out.wav>
timeline.json: [{"clip": "ui_ask", "start": 17.5, "trim": 1.0, "len": 30.1}, ...] (positions in the final video)
"""
import json, pathlib, sys, wave
import numpy as np

SR = 44100
rng = np.random.default_rng(11)
S = pathlib.Path(__file__).parent
CLIPS = S / "clips"


def env(n, attack, release):
    a, r = int(attack * SR), int(release * SR)
    e = np.ones(n)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] *= np.linspace(1, 0, r)
    return e


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def add(buf, sig, at, pan=0.0):
    i = int(at * SR)
    if i >= len(buf): return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig), 0] += sig * (1 - pan) ** 0.5 / 2 ** 0.5 * 1.41
    buf[i:i + len(sig), 1] += sig * (1 + pan) ** 0.5 / 2 ** 0.5 * 1.41


def music(total):
    out = np.zeros((int(total * SR) + SR, 2))
    bpm = 88; beat = 60 / bpm; bar = 4 * beat
    # Am9 - Fmaj7 - C(add9) - G6: a hopeful loop that sits under narration-free captions
    chords = [[57, 60, 64, 67, 71], [53, 57, 60, 64, 69], [48, 55, 60, 62, 64], [55, 59, 62, 64, 67]]
    bass = [45, 41, 48, 43]
    nbars = int(total / bar) + 1
    for b in range(nbars):
        t0, ch = b * bar, chords[b % 4]
        n = int(bar * SR * 1.15); t = np.arange(n) / SR
        # pad: soft detuned partials, slow swell
        pad = np.zeros(n)
        for m in ch[:4]:
            for d in (0.996, 1.004):
                f = hz(m) * d
                pad += np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)
        add(out, pad * env(n, 0.9, 1.0) * 0.010, t0)
        # bass on beats 1 and 3
        for k in (0, 2):
            nb = int(beat * 1.9 * SR); tb = np.arange(nb) / SR
            s = np.sin(2 * np.pi * hz(bass[b % 4]) * tb) + 0.3 * np.sin(4 * np.pi * hz(bass[b % 4]) * tb)
            add(out, s * np.exp(-tb * 2.2) * env(nb, 0.01, 0.1) * 0.055, t0 + k * beat)
        if b == 0 or t0 > total - bar * 1.5:
            continue  # intro and outro: pad + bass only
        # plucked arpeggio in eighths, one octave up, with a soft echo
        pattern = [0, 2, 4, 2, 1, 3, 4, 3]
        for k, idx in enumerate(pattern):
            npl = int(0.6 * SR); tp = np.arange(npl) / SR; f = hz(ch[idx] + 12)
            s = (np.sin(2 * np.pi * f * tp) + 0.35 * np.sin(4 * np.pi * f * tp) + 0.1 * np.sin(6 * np.pi * f * tp)) * np.exp(-tp * 7)
            s *= env(npl, 0.003, 0.05)
            pan = (-0.35, 0.35)[k % 2]
            add(out, s * 0.030, t0 + k * beat / 2, pan)
            add(out, s * 0.011, t0 + k * beat / 2 + beat * 0.75, -pan)
        # soft kick on 1 and 3, brushed hat on the off-beats
        for k in (0, 2):
            nk = int(0.25 * SR); tk = np.arange(nk) / SR
            f = 55 + 70 * np.exp(-tk * 30)
            add(out, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tk * 14) * 0.10, t0 + k * beat)
        for k in range(4):
            nh = int(0.06 * SR); th = np.arange(nh) / SR
            noise = np.diff(rng.standard_normal(nh + 1))
            add(out, noise * np.exp(-th * 70) * 0.008, t0 + k * beat + beat / 2, 0.2)
    n = len(out); fade = int(3.5 * SR); out[-fade - SR:-SR] *= np.linspace(1, 0, fade)[:, None]; out[-SR:] = 0
    out[: int(1.5 * SR)] *= np.linspace(0, 1, int(1.5 * SR))[:, None]
    return out[: int(total * SR)]


def _modes(n, freqs, decays, amps):
    """Impulse response of a few damped resonances (keycap, plate, switch housing)."""
    t = np.arange(n) / SR
    return sum(a * np.sin(2 * np.pi * f * t + rng.random() * 6) * np.exp(-t / d) for f, d, a in zip(freqs, decays, amps))


def _hit(n, freqs, decays, amps, burst_ms=1.2):
    """Excite the resonances with a short noise burst: a hard plastic/metal strike."""
    nb = max(8, int(burst_ms / 1000 * SR))
    burst = rng.standard_normal(nb) * np.hanning(nb)
    return np.convolve(burst, _modes(n, freqs, decays, amps))[:n]


def mech_key(kind):
    """Mechanical keyboard (clicky/tactile switch on a plate): click, bottom-out clack, return clack."""
    j = lambda x: x * rng.uniform(0.93, 1.07)
    n = int(0.16 * SR); out = np.zeros(n)
    if kind == "click":   # mouse button: tight, dry tick
        return _hit(int(0.03 * SR), [j(4200), j(6800), j(2600)], [0.0012, 0.0008, 0.002], [1, .6, .5], 0.4) * 0.5
    big = kind in ("space", "enter")
    # 1) switch click: bright, very short
    click = _hit(int(0.02 * SR), [j(3600), j(5400), j(7900)], [0.0015, 0.001, 0.0007], [1, .8, .5], 0.5) * 0.55
    # 2) bottom-out ~8 ms later: keycap hits the plate; lower, woodier on big keys
    body_f = [j(520), j(1150), j(1900), j(2900)] if big else [j(780), j(1500), j(2400), j(3700)]
    body = _hit(int(0.06 * SR), body_f, [0.012, 0.007, 0.005, 0.003], [1, .7, .5, .35], 1.5) * (1.25 if big else 1.0)
    # 3) return stroke ~75-105 ms later: same parts, quieter
    up = _hit(int(0.04 * SR), [f * 1.08 for f in body_f], [0.006, 0.004, 0.003, 0.002], [1, .7, .5, .35], 1.0) * 0.35
    d0 = int(rng.uniform(0.006, 0.010) * SR); u0 = int(rng.uniform(0.075, 0.105) * SR)
    out[:len(click)] += click
    out[d0:d0 + len(body)] += body
    out[u0:u0 + len(up)] += up
    if big:               # stabiliser wire rattle
        r0 = d0 + int(0.005 * SR); rat = _hit(int(0.02 * SR), [j(2200), j(3300)], [0.003, 0.002], [1, .6], 0.6) * 0.3
        out[r0:r0 + len(rat)] += rat
    return out / (np.abs(out).max() + 1e-9) * rng.uniform(0.8, 1.0) * (1.15 if big else 1.0)


def soft_key(kind):
    """First version: soft, rounded click + low thock."""
    if kind == "click":   # mouse button: short bright tick
        n = int(0.03 * SR); t = np.arange(n) / SR
        tick = np.diff(rng.standard_normal(n + 1)) * np.exp(-t * 900) * 0.35
        return tick + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 400) * 0.12
    n = int(0.07 * SR); t = np.arange(n) / SR
    low = {"key": 230, "space": 150, "enter": 140}[kind] * rng.uniform(0.92, 1.08)
    vol = {"key": 1.0, "space": 1.25, "enter": 1.4}[kind] * rng.uniform(0.8, 1.05)
    click = np.diff(rng.standard_normal(n + 1)) * np.exp(-t * 650) * 0.30      # switch contact
    thock = np.sin(2 * np.pi * low * t) * np.exp(-t * 85) * 0.30                  # keycap bottoming out
    upper = np.sin(2 * np.pi * low * 3.7 * t) * np.exp(-t * 160) * 0.07
    release = np.zeros(n); r0 = int(rng.uniform(0.045, 0.06) * SR)               # key coming back up
    release[r0:] = np.diff(rng.standard_normal(n - r0 + 1)) * np.exp(-np.arange(n - r0) / SR * 900) * 0.08
    return (click + thock + upper + release) * vol


def keypress(kind, mech=0.5):
    """Blend of the soft and the mechanical key: crisp but not harsh."""
    a, b = soft_key(kind), mech_key(kind)
    n = max(len(a), len(b)); a = np.pad(a, (0, n - len(a))); b = np.pad(b, (0, n - len(b)))
    a /= np.abs(a).max() + 1e-9
    return (1 - mech) * a + mech * b


MUSIC_GAIN = 0.42   # music peak level: bed sits ~-21.5 LUFS, keys clearly on top


def main(timeline_path, total, out_path):
    total = float(total)
    mix = music(total)
    mix *= MUSIC_GAIN / max(1e-9, np.abs(mix).max())   # music peaks at MUSIC_GAIN
    offsets = json.loads((CLIPS / "offsets.json").read_text())
    for seg in json.loads(pathlib.Path(timeline_path).read_text()):
        f = CLIPS / f"{seg['clip']}.events.json"
        if not f.exists(): continue
        e = json.loads(f.read_text())
        # Terminal replays type ~20 chars/s; sounding every one is a buzz. Keep at most one key sound
        # per MIN_GAP there, a little softer, so it reads as brisk typing instead.
        term = seg["clip"].startswith("term")
        gap, vol, last = (0.12, 0.85, -1.0) if term else (0.0, 1.2, -1.0)
        for t, kind in e["events"]:
            vt = t - e["t_open"] + offsets.get(seg["clip"], 0.0)        # time inside the recorded clip
            if not (seg["trim"] <= vt <= seg["trim"] + seg["len"]) or (vt - last < gap and kind != "enter"):
                continue
            last = vt
            add(mix, keypress(kind) * vol, seg["start"] + vt - seg["trim"], rng.uniform(-0.15, 0.15))
    over = np.abs(mix) > 0.8                            # soft-limit only the rare overlapping peaks
    mix[over] = np.sign(mix[over]) * (0.8 + 0.19 * np.tanh((np.abs(mix[over]) - 0.8) / 0.19))
    pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print("wrote", out_path, f"{total:.1f}s")


if __name__ == "__main__":
    main(*sys.argv[1:4])
