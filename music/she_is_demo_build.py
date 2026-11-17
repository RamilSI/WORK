#!/usr/bin/env python3
"""Our theme in Gogol Center 2019 hall language: strings + electronics + space.
About 8 minutes — twice the live She Is clip. Not a rip of Agraba's recording.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np

SR = 44100
BPM = 80.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT  # 3.0 s
OUT = Path(__file__).resolve().parent / "She-Is-Not-a-Name-I-Say-demo.wav"


def t_axis(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def env_adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    ea, ed, er = int(a * SR), int(d * SR), int(r * SR)
    es = max(0, n - ea - ed - er)
    parts = []
    if ea:
        parts.append(np.linspace(0.0, 1.0, ea, endpoint=False))
    if ed:
        parts.append(np.linspace(1.0, s, ed, endpoint=False))
    if es:
        parts.append(np.full(es, s))
    if er:
        parts.append(np.linspace(s, 0.0, er, endpoint=True))
    e = np.concatenate(parts) if parts else np.zeros(n)
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n]


def iir_lp(x: np.ndarray, cutoff: float) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    dt = 1.0 / SR
    a = dt / (1.0 / (2 * np.pi * cutoff) + dt)
    b = 1.0 - a
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = a * v + b * acc
        y[i] = acc
    return y


def iir_hp(x: np.ndarray, cutoff: float) -> np.ndarray:
    return x - iir_lp(x, cutoff)


def place(mix: np.ndarray, audio: np.ndarray, at_sec: float) -> None:
    start = int(at_sec * SR)
    if start >= len(mix):
        return
    audio = np.asarray(audio, dtype=np.float64)
    end = min(len(mix), start + len(audio))
    mix[start:end] += audio[: end - start]


def sine_vib(freq: float, n: int, amp: float, vib_hz: float = 5.0, cents: float = 7.0) -> np.ndarray:
    t = t_axis(n)
    depth = freq * (2 ** (cents / 1200.0) - 1.0)
    inst = freq + depth * np.sin(2 * np.pi * vib_hz * t)
    ph = 2 * np.pi * np.cumsum(inst) / SR
    return np.sin(ph) * amp


def analog_pad(freqs: list[float], n: int, amp: float) -> np.ndarray:
    t = t_axis(n)
    y = np.zeros(n)
    for f in freqs:
        for det, a in ((-1.8, 0.3), (0.0, 0.48), (2.0, 0.28)):
            y += a * np.sin(2 * np.pi * (f + det) * t)
            y += 0.14 * np.sin(4 * np.pi * (f + det) * t)
    y *= env_adsr(n, 1.2, 0.7, 0.72, 1.6)
    return np.tanh(iir_lp(y, 1050) * amp * 1.1)


def bowed(freq: float, n: int, amp: float, attack: float = 0.55) -> np.ndarray:
    y = sine_vib(freq, n, 1.0, vib_hz=5.2, cents=8.0)
    y += 0.42 * sine_vib(freq * 2, n, 1.0, vib_hz=5.5, cents=6.0)
    y += 0.18 * sine_vib(freq * 3, n, 1.0, vib_hz=4.7, cents=5.0)
    y += 0.07 * sine_vib(freq * 4, n, 1.0, vib_hz=5.0, cents=4.0)
    y *= env_adsr(n, attack, 0.45, 0.7, 1.3)
    return iir_lp(y, 3400) * amp


def cello(freq: float, n: int, amp: float) -> np.ndarray:
    y = sine_vib(freq, n, 0.8, vib_hz=3.5, cents=4.0)
    y += 0.28 * sine_vib(freq * 2, n, 0.8, vib_hz=3.8, cents=3.5)
    y *= env_adsr(n, 0.9, 0.4, 0.82, 1.4)
    return iir_lp(y, 480) * amp


def live_pulse(n: int, amp: float = 0.07) -> np.ndarray:
    """Quiet synth-floor pulse, not a kit. ~10% of the bed."""
    t = t_axis(n)
    freq = 46 * np.exp(-t * 7.5) + 27
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    return iir_lp(body * np.exp(-t * 4.0), 65) * amp


def hall(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Short + long room, like a theatre, not a cavern."""
    taps = [(29, 0.22, 18), (67, 0.16, -22), (113, 0.12, 31), (241, 0.09, -40), (487, 0.06, 55)]
    wl, wr = left.copy(), right.copy()
    for ms, g, spread in taps:
        d = int(ms * SR / 1000.0)
        sl = int(abs(spread) * SR / 1000.0)
        if d >= len(left):
            continue
        wl[d:] += left[:-d] * g
        wr[d:] += right[:-d] * g
        if sl and sl < len(left) - d:
            if spread > 0:
                wr[d + sl :] += left[: -(d + sl)] * (g * 0.35)
            else:
                wl[d + sl :] += right[: -(d + sl)] * (g * 0.35)
    return wl, wr


def say_line(text: str, voice: str, rate: int, path: Path) -> np.ndarray:
    aiff = path.with_suffix(".aiff")
    wav = path.with_suffix(".wav")
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff), "-ac", "1", "-ar", str(SR), str(wav)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    import wave as wavlib

    with wavlib.open(str(wav), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0


def vocal_fx(x: np.ndarray, wet: float = 0.58) -> np.ndarray:
    x = iir_hp(x, 90)
    echo = np.zeros_like(x)
    d1, d2, d3 = int(0.18 * SR), int(0.37 * SR), int(0.71 * SR)
    if d1 < len(x):
        echo[d1:] += x[:-d1] * 0.48
    if d2 < len(x):
        echo[d2:] += x[:-d2] * 0.28
    if d3 < len(x):
        echo[d3:] += x[:-d3] * 0.14
    return iir_lp(x * (1 - wet) + echo * wet, 4200)


def quartet(chord: list[float], n: int, gain: float) -> tuple[np.ndarray, np.ndarray]:
    # stronger strings than the last sketch
    vln1 = bowed(chord[-1], n, 0.072 * gain, attack=0.5)
    vln2 = bowed(chord[-2] if len(chord) > 2 else chord[-1] * 0.75, n, 0.062 * gain, attack=0.6)
    vla = bowed(chord[1] if len(chord) > 1 else chord[0] * 2, n, 0.055 * gain, attack=0.7)
    cel = cello(chord[0], n, 0.13 * gain)
    left = vln1 * 0.55 + vln2 * 0.25 + vla * 0.85 + cel * 1.05
    right = vln1 * 1.05 + vln2 * 0.95 + vla * 0.35 + cel * 0.82
    return left, right


def motif(notes: list[float], n: int, amp: float) -> np.ndarray:
    chunk = max(1, n // len(notes))
    y = np.zeros(n)
    for i, f in enumerate(notes):
        start = i * chunk
        if start >= n:
            break
        csz = min(chunk, n - start)
        y[start : start + csz] += bowed(f, csz, amp, attack=0.22)
    return y


def main() -> None:
    rng = np.random.default_rng(19)
    n_bars = 160  # 8:00 at 80 BPM
    total = int(n_bars * BAR * SR)
    left = np.zeros(total)
    right = np.zeros(total)

    am = [110.0, 164.81, 220.0, 261.63, 329.63]
    fmaj = [87.31, 174.61, 220.0, 261.63, 349.23]
    cmaj = [130.81, 164.81, 196.0, 261.63, 329.63]
    em = [82.41, 164.81, 196.0, 246.94, 329.63]
    ebm = [155.56, 185.0, 233.08, 311.13]
    verse = [am, fmaj, cmaj, em]
    chorus = [am, em, fmaj, cmaj]
    shadow = [ebm, ebm, am, am]

    nbar = int(BAR * SR)
    pulse = live_pulse(int(0.62 * SR), 0.065)
    cache: dict[tuple, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    def stem(chord: tuple, gain: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        key = (chord, round(gain, 2))
        if key not in cache:
            ch = list(chord)
            pad = analog_pad(ch, nbar, 0.046)
            ql, qr = quartet(ch, nbar, gain)
            cache[key] = (pad, ql, qr)
        return cache[key]

    def section(bar: int) -> str:
        if bar < 16:
            return "hall"
        if bar < 48:
            return "verse1"
        if bar < 64:
            return "lift"
        if bar < 96:
            return "chorus1"
        if bar < 112:
            return "ensemble"
        if bar < 144:
            return "verse2"
        return "final"

    for bar in range(n_bars):
        kind = section(bar)
        at = bar * BAR
        if kind == "ensemble":
            prog = shadow
            gain = 1.32
            pad_on = 0.7
        elif kind in ("chorus1", "final"):
            prog = chorus
            gain = 1.18 if kind == "chorus1" else 1.05
            pad_on = 0.85
        elif kind == "lift":
            prog = verse
            gain = 1.12
            pad_on = 0.8
        else:
            prog = verse
            gain = 1.08 if kind == "hall" else 1.08
            pad_on = 1.0 if kind == "hall" else 0.78

        chord = tuple(prog[bar % 4])
        pad, ql, qr = stem(chord, gain)
        place(left, pad * 0.9 * pad_on, at)
        place(right, np.roll(pad, 140) * 1.05 * pad_on, at)
        place(left, ql, at)
        place(right, qr, at)

        if kind == "verse1" and bar % 2 == 0:
            place(left, pulse * 0.55, at)
            place(right, pulse * 0.5, at)
        elif kind == "lift":
            place(left, pulse * 0.7, at)
            place(right, pulse * 0.62, at)
        elif kind == "chorus1":
            place(left, pulse * 0.82, at)
            place(right, pulse * 0.74, at)
            ghost = pulse * 0.32
            place(left, ghost, at + 2 * BEAT)
            place(right, ghost * 0.9, at + 2 * BEAT)
        elif kind == "ensemble" and bar % 2 == 0:
            place(left, pulse * 0.68, at)
            place(right, pulse * 0.6, at)
        elif kind == "verse2" and bar % 2 == 0:
            place(left, pulse * 0.58, at)
            place(right, pulse * 0.52, at)
        elif kind == "final" and bar % 2 == 0:
            place(left, pulse * 0.4, at)
            place(right, pulse * 0.36, at)

        if kind == "hall" and bar == 0:
            line = motif([440.0, 392.0, 349.23, 329.63], int(8 * BAR * SR), 0.068)
            place(left, line * 0.85, at)
            place(right, np.roll(line, 240) * 1.05, at)
        if kind == "lift" and bar == 48:
            line = motif([220.0, 261.63, 329.63, 392.0, 440.0], int(8 * BAR * SR), 0.06)
            place(left, line * 0.9, at)
            place(right, np.roll(line, 180) * 1.0, at)
        if kind == "ensemble" and bar == 96:
            line = motif([329.63, 349.23, 392.0, 440.0, 523.25, 440.0, 392.0, 329.63], int(8 * BAR * SR), 0.07)
            place(left, line * 0.85, at)
            place(right, np.roll(line, 200) * 1.05, at)
        if kind == "final" and bar == 144:
            line = motif([440.0, 329.63, 261.63, 220.0], int(8 * BAR * SR), 0.05)
            place(left, line * 0.8, at)
            place(right, np.roll(line, 280) * 0.9, at)

        if bar % 8 == 0:
            air_n = int(0.7 * SR)
            air = iir_hp(rng.normal(0, 1, air_n), 2800) * env_adsr(air_n, 0.03, 0.1, 0.2, 0.4) * 0.014
            place(left, air, at)
            place(right, air * 0.7, at + 0.05)

    tmp = Path(tempfile.mkdtemp(prefix="gogol_theme_"))
    # Our theme, stretched over the hall form
    vocals = [
        # ~5% nod: wordless live-hall "she is", not Agraba's recording
        (4, "she", "Whisper", 82, 0.48),
        (8, "is", "Whisper", 76, 0.48),
        (12, "she is", "Whisper", 72, 0.44),
        (16, "She is not a name I say", "Whisper", 110, 0.42),
        (20, "She is the air that stays", "Whisper", 108, 0.42),
        (24, "After every door I close", "Whisper", 110, 0.4),
        (28, "After every light I waste", "Whisper", 105, 0.4),
        (32, "She is not a word I keep", "Whisper", 108, 0.42),
        (36, "She is older than the speech", "Whisper", 102, 0.4),
        (40, "If I try to hold her still", "Whisper", 108, 0.4),
        (44, "She becomes the thing I miss", "Whisper", 98, 0.44),
        (48, "If I call, the signal bends", "Samantha", 118, 0.3),
        (56, "If I wait, you start again", "Samantha", 114, 0.3),
        (64, "She is not a name I say", "Samantha", 112, 0.34),
        (68, "Say it once, she slips away", "Samantha", 114, 0.32),
        (72, "Say it twice, the room goes thin", "Samantha", 110, 0.32),
        (76, "Say it three, I'm in", "Samantha", 105, 0.34),
        (80, "She is not a name I say", "Samantha", 110, 0.34),
        (84, "She is what the dark became", "Samantha", 108, 0.32),
        (88, "I can love her, I can wait", "Samantha", 108, 0.32),
        (92, "I just cannot make her stay", "Samantha", 98, 0.36),
        (100, "she is", "Whisper", 74, 0.4),
        (108, "she is", "Whisper", 70, 0.38),
        (112, "She is not a face I draw", "Whisper", 108, 0.4),
        (116, "She is heat along the floor", "Whisper", 108, 0.4),
        (120, "Like a signal in the wire", "Whisper", 108, 0.38),
        (124, "Like a weather I ignore", "Whisper", 104, 0.4),
        (128, "Don't you call her", "Whisper", 100, 0.36),
        (132, "Don't you name her", "Whisper", 100, 0.36),
        (136, "Let her move the static", "Whisper", 102, 0.38),
        (140, "Let her be the hour", "Whisper", 96, 0.4),
        (144, "She is not a name I say", "Whisper", 92, 0.44),
        (148, "She is not a name", "Whisper", 88, 0.42),
        (152, "She is", "Whisper", 78, 0.5),
        (156, "She is", "Whisper", 70, 0.48),
    ]
    for i, (bar, text, voice, rate, amp) in enumerate(vocals):
        raw = say_line(text, voice, rate, tmp / f"v{i}")
        fx = vocal_fx(raw, wet=0.62 if voice == "Samantha" else 0.5) * amp
        at = bar * BAR + 0.15
        place(left, fx * 0.92, at)
        place(right, np.roll(fx, 130) * 1.0, at)

    left, right = hall(left, right)
    fade = int(8.0 * SR)
    left[-fade:] *= np.linspace(1, 0, fade)
    right[-fade:] *= np.linspace(1, 0, fade)

    stereo = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(stereo)) or 1.0)
    stereo = stereo / peak * 0.89
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    import wave as wavlib

    with wavlib.open(str(OUT), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"WROTE {OUT}  peak={peak:.3f}  duration={len(left)/SR:.1f}s")


if __name__ == "__main__":
    main()
