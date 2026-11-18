"""Magenta Hour's three background tracks: original synthwave pieces, written here note by note.

    python3 -I themes/magenta-hour/make-music.py [name ...]   (needs numpy and scipy; afconvert, built into macOS, encodes the .m4a)

Nothing sampled or downloaded: every sound is synthesised below (detuned saw pads, a pulsing bass,
a plucked arpeggio, a soft lead, drum-machine kick/snare/hats), so the tracks are ours and free to ship.
Each is written as a whole piece with an ending (the last bar drops to the pad and one bass note, the
reverb rings out), not a seamless loop: the tracks play one after another, and a gap after an ending
sounds like the next song where one mid-groove sounds broken.

Writes plugins/magenta-hour/music/<name>.m4a (AAC, what the plugin plays; tools/build.py copies them into
the picker) and <name>.wav beside this file (the master, not committed). With names, only those tracks.
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
TAIL = int(4 * SR)
HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "plugins" / "magenta-hour" / "music"

# The song being rendered: configure() sets these from one of SONGS before render() runs, and the parts read them.
NAME: str
BPM: float
BEAT: float          # seconds
BAR: float           # seconds
BARS: int
LOOP: int            # samples
CHORDS: list         # (name, MIDI notes, bass root): one chord per two bars, the 8-bar cycle looped
CYCLES: list         # per 8 bars: which parts play and how open the pad filter is
PHRASE: list         # the lead's notes: (bar offset in the cycle, beat, length in beats, MIDI note)
rng: np.random.Generator


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def lowpass(x, cutoff, order=2):
    return sosfilt(butter(order, min(cutoff, SR * 0.45), "low", fs=SR, output="sos"), x)


def highpass(x, cutoff, order=2):
    return sosfilt(butter(order, cutoff, "high", fs=SR, output="sos"), x)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def saw(freq, n, phase=0.0):
    """A band-limited-ish saw: a naive saw softened by a gentle lowpass downstream."""
    t = np.arange(n) / SR
    return 2 * ((freq * t + phase) % 1.0) - 1


def adsr(n, a, d, s, r, hold):
    """Attack, decay, sustain level, release (seconds); `hold` is how long the note is held."""
    env = np.zeros(n)
    ai, di, hi, ri = (int(v * SR) for v in (a, d, hold, r))
    ai = max(ai, 1)
    env[:min(ai, n)] = np.linspace(0, 1, ai)[:n]
    end = min(ai + di, n)
    if end > ai:
        env[ai:end] = np.linspace(1, s, di)[: end - ai]
    if hi > ai + di:
        env[ai + di:min(hi, n)] = s
    level = env[min(hi, n) - 1] if hi > 0 else s
    rend = min(hi + ri, n)
    if rend > hi:
        env[hi:rend] = np.linspace(level, 0, ri)[: rend - hi]
    return env


class Mix:
    def __init__(self):
        self.buf = np.zeros((2, LOOP + TAIL))

    def add(self, sig, start_s, gain=1.0, pan=0.0):
        """Mono `sig` placed at `start_s` seconds, equal-power pan (-1 left, 1 right)."""
        i = int(round(start_s * SR))
        sig = sig[: max(0, self.buf.shape[1] - i)]
        a = (pan + 1) * np.pi / 4
        self.buf[0, i:i + len(sig)] += sig * gain * np.cos(a)
        self.buf[1, i:i + len(sig)] += sig * gain * np.sin(a)


# ------------------------------------------------------------------ the parts

def chord_at(bar):
    return CHORDS[(bar // 2) % 4]


def pad(mix: Mix):
    """Detuned saw stack per chord, slow swell, stereo spread by voice."""
    for bar in range(0, BARS, 2):
        _, notes, _ = chord_at(bar)
        cyc = CYCLES[bar // 8]
        start = bar * BAR
        hold = 2 * BAR
        n = int((hold + 1.6) * SR)
        env = adsr(n, 0.9, 0.6, 0.85, 1.6, hold)
        for k, m in enumerate(notes):
            for v, cents in enumerate((-9, -3, 4, 10)):
                f = hz(m) * 2 ** (cents / 1200)
                sig = saw(f, n, phase=rng.random())
                sig = lowpass(sig, cyc["pad_cut"] + 120 * k, order=2)
                pan = (-0.7 + 1.4 * v / 3) * 0.8
                mix.add(sig * env, start, gain=0.022, pan=pan)


def bass(mix: Mix):
    """Eighth-note pulse on the root, octave jump on the last eighth of each bar; plucky filter."""
    for bar in range(BARS):
        _, _, root = chord_at(bar)
        if bar == BARS - 1:   # the ending: one long root note under the pad
            n = int((BAR + 2.5) * SR)
            env = adsr(n, 0.01, 0.4, 0.6, 2.0, BAR)
            sig = lowpass(0.6 * saw(hz(root), n) + 0.4 * saw(hz(root) * 1.004, n, 0.3), 420)
            mix.add(sig * env, bar * BAR, gain=0.30)
            continue
        for e in range(8):
            m = root + (12 if e == 7 else 0)
            n = int(0.42 * SR)
            env = adsr(n, 0.004, 0.18, 0.35, 0.08, BEAT / 2 * 0.85)
            f = hz(m)
            sig = 0.6 * saw(f, n) + 0.4 * saw(f * 1.004, n, 0.3)
            filt_env = 260 + 900 * np.exp(-np.arange(n) / (0.07 * SR))
            # filter sweep: split into short blocks with their own cutoff
            out = np.zeros(n)
            blk = 512
            for b0 in range(0, n, blk):
                out[b0:b0 + blk] = lowpass(sig[b0:b0 + blk + 256], filt_env[b0], order=2)[:len(out[b0:b0 + blk])]
            mix.add(out * env, bar * BAR + e * BEAT / 2, gain=0.30, pan=0.0)


def arp(mix: Mix):
    """Sixteenth-note pluck through the chord, with a dotted-eighth ping-pong echo."""
    pattern = [0, 2, 3, 4, 3, 2, 1, 2]
    dry = Mix()
    for bar in range(BARS):
        if not CYCLES[bar // 8]["arp"] or bar == BARS - 1:
            continue
        _, notes, _ = chord_at(bar)
        for s in range(16):
            m = notes[pattern[s % 8]] + 12
            n = int(0.25 * SR)
            env = np.exp(-np.arange(n) / (0.07 * SR))
            t = np.arange(n) / SR
            sig = np.sign(np.sin(2 * np.pi * hz(m) * t)) * 0.5 + 0.5 * saw(hz(m) * 1.003, n)
            sig = lowpass(sig, 2600, order=2)
            accent = 1.0 if s % 4 == 0 else 0.7
            dry.add(sig * env, bar * BAR + s * BEAT / 4, gain=0.05 * accent, pan=0.0)
    # dotted-eighth ping-pong
    d = int(0.75 * BEAT * SR)
    wet = np.zeros_like(dry.buf)
    mono = dry.buf[0] + dry.buf[1]
    for k, g in enumerate((0.45, 0.3, 0.2, 0.12), start=1):
        side = 0 if k % 2 else 1
        wet[side, k * d:] += mono[: wet.shape[1] - k * d] * g
    mix.buf += dry.buf + lowpass(wet, 3000)


def lead(mix: Mix):
    """A soft, slow lead in the cycles that have one: saw + vibrato, long notes, echoed."""
    dry = Mix()
    for ci, cyc in enumerate(CYCLES):
        if not cyc["lead"]:
            continue
        for bar_off, beat, length, m in PHRASE:
            hold = length * BEAT * 0.95
            n = int((hold + 0.6) * SR)
            t = np.arange(n) / SR
            vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.6, 0, 1)
            f = hz(m)
            phase = np.cumsum(f * vib) / SR
            sig = 0.5 * (2 * (phase % 1) - 1) + 0.5 * (2 * ((phase * 1.005) % 1) - 1)
            sig = lowpass(sig, 1900, order=2)
            env = adsr(n, 0.08, 0.3, 0.7, 0.5, hold)
            dry.add(sig * env, (ci * 8 + bar_off) * BAR + beat * BEAT, gain=0.06, pan=0.1)
    d = int(0.75 * BEAT * SR)
    wet = np.zeros_like(dry.buf)
    for k, g in enumerate((0.35, 0.2, 0.1), start=1):
        wet[:, k * d:] += dry.buf[:, : wet.shape[1] - k * d] * g
    mix.buf += dry.buf + lowpass(wet, 2500)


def kick():
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    f = 45 + 75 * np.exp(-t / 0.035)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16)
    click = lowpass(rng.standard_normal(n), 3000) * np.exp(-t / 0.004) * 0.3
    return body + click


def snare():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05) * 0.5
    noise = bandpass(rng.standard_normal(n), 900, 7000) * np.exp(-t / 0.12) * 0.6
    return tone + noise


def hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    return highpass(rng.standard_normal(n), 7000) * np.exp(-t / (0.08 if open_ else 0.015))


def drums(mix: Mix, duck: np.ndarray):
    """Four-on-the-floor kick, snare on 2 and 4 (big gated room), eighth hats; `duck` gets the kick envelope."""
    room = Mix()
    K, S = kick(), snare()
    for bar in range(BARS):
        style = CYCLES[bar // 8]["drums"]
        if style == "none":
            continue
        if bar == BARS - 1:   # the ending: one last kick on the downbeat, then the room rings
            mix.add(K, bar * BAR, gain=0.42)
            continue
        for beat in range(4):
            at = bar * BAR + beat * BEAT
            kg = 0.55 if style == "full" else 0.42
            mix.add(K, at, gain=kg)
            i = int(at * SR)
            duck[i:i + int(0.28 * SR)] = np.minimum(duck[i:i + int(0.28 * SR)], 1 - 0.55 * np.exp(-np.arange(int(0.28 * SR)) / (0.09 * SR)))
            if beat in (1, 3) and (style == "full" or bar % 2 == 1):
                g = 0.30 if style == "full" else 0.2
                mix.add(S, at, gain=g)
                room.add(S, at, gain=g)
        for e in range(8):
            g = 0.05 if e % 2 else 0.035
            mix.add(hat(open_=(e == 7 and bar % 2 == 1)), bar * BAR + e * BEAT / 2, gain=g, pan=0.25)
    # the 80s gated snare room: a bright, short burst of reverb cut off hard
    n = int(0.32 * SR)
    ir = rng.standard_normal((2, n)) * np.linspace(1, 0.7, n)
    ir[:, int(0.28 * SR):] *= np.linspace(1, 0, n - int(0.28 * SR))
    for ch in range(2):
        mix.buf[ch] += fftconvolve(room.buf[ch], ir[ch])[: mix.buf.shape[1]] * 0.018


def reverb(x, seconds=2.6, wet=0.22):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros_like(x)
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-t / (seconds / 6.9))
        ir = lowpass(ir, 5000)
        ir /= np.sqrt(np.sum(ir ** 2))
        out[ch] = fftconvolve(x[ch], ir)[: x.shape[1]]
    return x + out * wet


def render():
    OUT.mkdir(exist_ok=True)
    music, beat = Mix(), Mix()
    duck = np.ones(LOOP + TAIL)
    pad(music)
    bass(music)
    arp(music)
    lead(music)
    drums(beat, duck)
    music.buf *= duck                    # the pumping sidechain against the kick
    mixed = reverb(music.buf, 2.8, 0.28) + reverb(beat.buf, 1.2, 0.08)
    # keep the ring-out (3 s past the last bar), fade its last half second, a 20 ms fade-in at the top
    loop = mixed[:, :LOOP + 3 * SR].copy()
    loop[:, -SR // 2:] *= np.linspace(1, 0, SR // 2)
    loop[:, :int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    loop = highpass(loop, 28)
    loop = np.tanh(loop * 1.3) / np.tanh(1.3)   # gentle glue
    loop *= 0.89 / np.max(np.abs(loop))          # peak about -1 dBFS
    pcm = (loop.T * 32767).astype("<i2")
    wav = HERE / f"{NAME}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    m4a = OUT / f"{NAME}.m4a"
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", "-b", "160000", str(wav), str(m4a)], check=True)
    rms = 20 * np.log10(np.sqrt(np.mean(loop ** 2)))
    print(f"{NAME}: {loop.shape[1] / SR:.1f} s piece, rms {rms:.1f} dBFS, wav {wav.stat().st_size / 1e6:.1f} MB, m4a {m4a.stat().st_size / 1e6:.2f} MB")



SONGS = [
    # 1. Magenta Hour: the theme's own piece
    dict(name="magenta-hour", bpm=92, seed=1985, chords=[
        ("Am9", [57, 60, 64, 67, 71], 45), ("Fmaj7", [53, 57, 60, 64, 69], 41),
        ("Cmaj7", [55, 60, 64, 67, 71], 48), ("G6", [55, 59, 62, 64, 67], 43)],
        cycles=[dict(drums="soft", arp=False, lead=False, pad_cut=1100), dict(drums="full", arp=True, lead=False, pad_cut=1700),
                dict(drums="full", arp=True, lead=True, pad_cut=2300), dict(drums="soft", arp=True, lead=False, pad_cut=1500)],
        phrase=[(0, 0, 3, 76), (0, 3, 1, 74), (1, 0, 4, 72), (2, 0, 2, 71), (2, 2, 2, 72), (3, 0, 4, 67),
                (4, 0, 3, 76), (4, 3, 1, 79), (5, 0, 4, 76), (6, 0, 2, 74), (6, 2, 2, 72), (7, 0, 4, 71)]),
    # 2. Causeway: faster and driving, F# minor (i - VI - III - VII), the lead twice
    dict(name="magenta-hour-2", bpm=104, seed=1986, chords=[
        ("F#m9", [54, 57, 61, 64, 68], 42), ("Dmaj7", [50, 54, 57, 61, 64], 38),
        ("Aadd9", [52, 57, 61, 64, 71], 45), ("E6", [52, 56, 59, 64, 68], 40)],
        cycles=[dict(drums="soft", arp=True, lead=False, pad_cut=1300), dict(drums="full", arp=True, lead=False, pad_cut=1900),
                dict(drums="full", arp=True, lead=True, pad_cut=2400), dict(drums="soft", arp=False, lead=False, pad_cut=1200),
                dict(drums="full", arp=True, lead=True, pad_cut=2200)],
        phrase=[(0, 0, 3, 73), (0, 3, 1, 71), (1, 0, 4, 69), (2, 0, 2, 69), (2, 2, 2, 73), (3, 0, 4, 66),
                (4, 0, 3, 76), (4, 3, 1, 73), (5, 0, 4, 71), (6, 0, 2, 68), (6, 2, 2, 71), (7, 0, 4, 64)]),
    # 3. Afterglow: slow and dreamy, B minor (VI - VII - v - i), drums only brushed in
    dict(name="magenta-hour-3", bpm=84, seed=1987, chords=[
        ("Gmaj7", [55, 59, 62, 66, 69], 43), ("A6", [57, 61, 64, 66, 69], 45),
        ("F#m7", [54, 57, 61, 64, 69], 42), ("Bm9", [50, 54, 57, 59, 61], 47)],
        cycles=[dict(drums="none", arp=False, lead=False, pad_cut=1000), dict(drums="soft", arp=True, lead=False, pad_cut=1500),
                dict(drums="soft", arp=True, lead=True, pad_cut=1900), dict(drums="none", arp=True, lead=True, pad_cut=1300)],
        phrase=[(0, 0, 3, 74), (0, 3, 1, 73), (1, 0, 4, 71), (2, 0, 2, 69), (2, 2, 2, 73), (3, 0, 4, 69),
                (4, 0, 3, 66), (4, 3, 1, 69), (5, 0, 4, 73), (6, 0, 2, 74), (6, 2, 2, 73), (7, 0, 4, 71)]),
]


def configure(song):
    """Point the module's song globals at one song (the parts read them as they render)."""
    global NAME, BPM, BEAT, BAR, BARS, LOOP, CHORDS, CYCLES, PHRASE, rng
    NAME, BPM = song["name"], song["bpm"]
    BEAT = 60 / BPM
    BAR = 4 * BEAT
    CYCLES = song["cycles"]
    BARS = 8 * len(CYCLES)
    LOOP = int(round(BARS * BAR * SR))
    CHORDS, PHRASE = song["chords"], song["phrase"]
    rng = np.random.default_rng(song["seed"])


def main():
    wanted = set(sys.argv[1:])
    for song in SONGS:
        if not wanted or song["name"] in wanted:
            configure(song)
            render()


if __name__ == "__main__":
    main()
