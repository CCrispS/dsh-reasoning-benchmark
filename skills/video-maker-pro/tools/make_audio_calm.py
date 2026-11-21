# -*- coding: utf-8 -*-
"""
make_audio.py

Procedural score + SFX for the short documentary
"两份开源项目声明背后的授权与署名争议"

Everything is synthesized with numpy only (no scipy, no external audio,
no downloads). 48 kHz / 16-bit / stereo PCM WAV via the stdlib `wave` module.

Outputs:
    audio/bgm/bed-a.wav
    audio/sfx/*.wav
    audio/manifest.json      (levels measured with ffmpeg volumedetect)

Run:
    PYTHONIOENCODING=utf-8 <python> tools/make_audio_calm.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
SR = 48000
SEED = 20261121

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]                    # 技能根目录
AUDIO = ROOT / "audio"
BGM_DIR = AUDIO / "bgm"
SFX_DIR = AUDIO / "sfx"

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or ""

BPM = 60.0
BEATS_PER_BAR = 4
BAR = BEATS_PER_BAR * 60.0 / BPM          # 4.0 s
BARS = 8
CYCLE = BAR * BARS                        # 32.0 s
REPEATS = 7
TOTAL = CYCLE * REPEATS                   # 224.0 s

CHORDS = {
    "Am": dict(notes=[45, 52, 57, 60], root=55.00),   # A2 E3 A3 C4
    "F":  dict(notes=[41, 48, 53, 57], root=43.65),   # F2 C3 F3 A3
    "C":  dict(notes=[48, 55, 60, 64], root=65.41),   # C3 G3 C4 E4
    "G":  dict(notes=[43, 50, 55, 59], root=49.00),   # G2 D3 G3 B3
    "Dm": dict(notes=[50, 57, 62, 65], root=73.42),   # D3 A3 D4 F4
    "E":  dict(notes=[40, 47, 52, 56], root=41.20),   # E2 B2 E3 G#3
}
PROGRESSION = ["Am", "F", "C", "G", "Am", "F", "Dm", "E"]

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def db2lin(d):
    return 10.0 ** (np.asarray(d, dtype=np.float64) / 20.0)


def lin2db(v, floor=1e-12):
    return 20.0 * np.log10(max(float(v), floor))


def rms(x):
    a = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(a * a)))


def peak(x):
    a = np.asarray(x, dtype=np.float64)
    return float(np.max(np.abs(a))) if a.size else 0.0


def midi_hz(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def raised_cos(x):
    x = np.clip(x, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def env_ar(n, attack_s, release_s):
    """raised-cosine attack, flat body, raised-cosine release."""
    t = np.arange(n, dtype=np.float64)
    a = raised_cos(t / max(attack_s * SR, 1.0))
    r = raised_cos((n - t) / max(release_s * SR, 1.0))
    return a * r


def add_wrapped(buf, start, sig):
    """add a (2, n) signal into a ring buffer at sample `start` (wraps)."""
    n = buf.shape[1]
    m = sig.shape[1]
    s = int(start) % n
    if m > n:
        raise ValueError("signal longer than buffer")
    end = s + m
    if end <= n:
        buf[:, s:end] += sig
    else:
        k = n - s
        buf[:, s:] += sig[:, :k]
        buf[:, :m - k] += sig[:, k:]


# --------------------------------------------------------------------------
# FIR design + convolution
# --------------------------------------------------------------------------


def fir_lp(fc, taps=513):
    fc = float(np.clip(fc, 15.0, SR * 0.45))
    m = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
    h = 2.0 * fc / SR * np.sinc(2.0 * fc / SR * m)
    h *= np.blackman(taps)
    h /= np.sum(h)
    return h


def fir_hp(fc, taps=513):
    h = -fir_lp(fc, taps)
    h[(taps - 1) // 2] += 1.0
    return h


def fir_bp(flo, fhi, taps=513):
    m = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
    h = (2.0 * fhi / SR * np.sinc(2.0 * fhi / SR * m)
         - 2.0 * flo / SR * np.sinc(2.0 * flo / SR * m))
    h *= np.blackman(taps)
    resp = np.abs(np.fft.rfft(h, 16384))
    h /= max(float(resp.max()), 1e-12)
    return h


def fftconv(x, h):
    """linear convolution along the last axis, output trimmed to len(x)."""
    x = np.asarray(x, dtype=np.float64)
    n = x.shape[-1]
    m = h.shape[0]
    nfft = 1 << int(np.ceil(np.log2(n + m)))
    H = np.fft.rfft(h, nfft)
    y = np.fft.irfft(np.fft.rfft(x, nfft, axis=-1) * H, nfft, axis=-1)
    return y[..., :n]


def circ_conv(x, h):
    """circular convolution along the last axis, same length."""
    n = x.shape[-1]
    H = np.fft.rfft(h, n)
    return np.fft.irfft(np.fft.rfft(x, axis=-1) * H, n=n, axis=-1)


# --------------------------------------------------------------------------
# short-time spectral mask (real time-varying band filter for noise)
# --------------------------------------------------------------------------


def spectral_mask(x, fc_fn, width_oct=1.1, n=1024, hop=256, tilt_db_oct=0.0):
    x = np.asarray(x, dtype=np.float64)
    w = np.hanning(n + 1)[:-1]
    padded = np.concatenate([x, np.zeros(n)])
    frames = np.lib.stride_tricks.sliding_window_view(padded, n)[::hop]
    nf = frames.shape[0]
    S = np.fft.rfft(frames * w, axis=1)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    freqs[0] = freqs[1]
    centers = np.maximum(fc_fn((np.arange(nf) * hop + n * 0.5) / SR), 25.0)
    lf = np.log2(freqs)[None, :]
    lc = np.log2(centers)[:, None]
    G = np.exp(-0.5 * ((lf - lc) / (width_oct * 0.55)) ** 2)
    if tilt_db_oct:
        G *= 10.0 ** (tilt_db_oct * (lf - lc) / 20.0)
    Y = np.fft.irfft(S * G, n=n, axis=1) * w
    out = np.zeros(x.size + n)
    nrm = np.zeros(x.size + n)
    for i in range(nf):
        a = i * hop
        out[a:a + n] += Y[i]
        nrm[a:a + n] += w * w
    out /= np.maximum(nrm, 1e-7)
    return out[:x.size]


# --------------------------------------------------------------------------
# genuinely time-varying lowpass (windowed frames, circular, COLA-exact)
# --------------------------------------------------------------------------


def tv_lowpass(x, fc_fn, order=2, block=2048):
    """x: (2, N) -> (2, N). fc_fn(t_seconds) -> cutoff Hz.

    Time-varying zero-phase lowpass: 4096-sample frames (hop 2048, periodic
    Hann), each spectrum multiplied by a Butterworth magnitude response whose
    cutoff follows the slow LFO (12 dB/oct, so the pad keeps some air instead
    of being brickwalled). Hann analysis+synthesis with w^2 renormalisation.
    Frames are taken and accumulated circularly so the file stays loopable.
    """
    L = block * 2
    N = x.shape[1]
    win = np.hanning(L + 1)[:-1]
    fr = np.fft.rfftfreq(L, 1.0 / SR)
    ar = np.arange(L)
    grid = np.geomspace(600.0, 3400.0, 90)
    mags = np.stack([1.0 / np.sqrt(1.0 + (fr / float(f)) ** (2 * order))
                     for f in grid])

    out = np.zeros((2, N + L))
    nrm = np.zeros(N + L)
    for i in range(N // block):
        s = i * block
        seg = x[:, (s - block + ar) % N]
        k = int(np.argmin(np.abs(np.log(grid / max(fc_fn((s + block) / SR), 40.0)))))
        Y = np.fft.irfft(np.fft.rfft(seg, n=L, axis=-1) * mags[k], n=L, axis=-1)
        out[:, s:s + L] += win * Y
        nrm[s:s + L] += win * win
    out[:, :L] += out[:, N:N + L]
    nrm[:L] += nrm[N:N + L]
    return out[:, :N] / np.maximum(nrm[None, :N], 1e-12)


# --------------------------------------------------------------------------
# synthetic reverb impulse response
# --------------------------------------------------------------------------


def make_ir(dur=2.2, rt60=2.0, seed=SEED + 500, predelay=0.018, dark=5200.0):
    n = int(dur * SR)
    pre = int(predelay * SR)
    t = np.arange(n, dtype=np.float64) / SR
    env = np.exp(-6.9078 * t / rt60)
    base = np.random.default_rng(seed).standard_normal(n)
    d = int(0.0009 * SR)
    out = np.zeros((2, n))
    for c in range(2):
        rng = np.random.default_rng(seed + 17 * c)
        if c == 0:
            h = base.copy()
        else:
            h = np.concatenate([np.zeros(d), base[:-d]])
            h = h + 0.25 * rng.standard_normal(n)
        h *= env
        h[t < predelay] = 0.0
        h = fftconv(h, fir_lp(dark, 129))
        h = fftconv(h, fir_hp(140.0, 257))
        # sparse early reflections for a little room shape
        for j, (dly, amp) in enumerate(((0.011, 0.55), (0.019, -0.40),
                                        (0.031, 0.30), (0.047, 0.20),
                                        (0.063, -0.15))):
            k = pre + int(dly * SR) + 3 * j
            if k < n:
                h[k] += amp * (1.0 if c == 0 else -0.7)
        e = np.sqrt(np.sum(h * h))
        out[c] = h / max(e, 1e-9)
    return out


# --------------------------------------------------------------------------
# BGM
# --------------------------------------------------------------------------


_PAD_TABLE = None


def _pad_table(size=4096):
    """Soft-saw wavetable: 12 harmonics at n**-1.3, fundamental amplitude 1.0."""
    global _PAD_TABLE
    if _PAD_TABLE is None:
        ph = np.arange(size, dtype=np.float64) / size
        w = np.zeros(size)
        for h in range(1, 13):
            w += (h ** -1.3) * np.sin(2.0 * np.pi * h * ph)
        _PAD_TABLE = w
    return _PAD_TABLE


def render_pad_note(freq, dur, amp, pan, rng, attack, release):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    det_l = rng.uniform(3.0, 6.0)
    det_r = rng.uniform(-6.0, -3.0)
    tab = _pad_table()
    size = tab.size
    x = np.zeros((2, n))
    for ch, det in ((0, det_l), (1, det_r)):
        f = freq * 2.0 ** (det / 1200.0)
        pos = ((f * t) % 1.0) * size
        i0 = pos.astype(np.int64)
        fr = pos - i0
        x[ch] = tab[i0] * (1.0 - fr) + tab[(i0 + 1) % size] * fr
    x *= env_ar(n, attack, release)
    gl = np.sqrt(0.5 * (1.0 - pan))
    gr = np.sqrt(0.5 * (1.0 + pan))
    x[0] *= amp * gl
    x[1] *= amp * gr
    return x


def build_pad_cycle(rng):
    n = int(CYCLE * SR)
    pad = np.zeros((2, n))
    pans = (-0.30, 0.28, -0.12, 0.38)
    for b, name in enumerate(PROGRESSION):
        notes = CHORDS[name]["notes"]
        for vi, m in enumerate(notes):
            amp = (0.100, 0.085, 0.072, 0.058)[vi]
            attack = rng.uniform(0.95, 1.35)
            release = rng.uniform(2.7, 3.4)
            pan = pans[(vi + b) % 4]
            sig = render_pad_note(midi_hz(m), BAR + release, amp, pan, rng,
                                  attack, release)
            add_wrapped(pad, int(b * BAR * SR), sig)
    return pad


def build_bass(rng, n_total):
    out = np.zeros((2, n_total))
    n_bars = int(TOTAL / BAR)
    for b in range(n_bars):
        name = PROGRESSION[b % BARS]
        f0 = CHORDS[name]["root"]
        dur = 0.55
        n = int(dur * SR)
        t = np.arange(n, dtype=np.float64) / SR
        env = raised_cos(t / 0.008) * np.exp(-t / 0.40)
        sig = np.sin(2.0 * np.pi * f0 * t) + 0.22 * np.sin(4.0 * np.pi * f0 * t)
        sig *= env * 0.058 * rng.uniform(0.92, 1.06)
        start = int(b * BAR * SR)
        add_wrapped(out, start, np.stack([sig, sig]))
    return out


def pluck(freq, dur, amp):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    env = (1.0 - np.exp(-t / 0.004)) * np.exp(-t / 0.16)
    s = (np.sin(2.0 * np.pi * freq * t)
         + 0.32 * np.sin(4.0 * np.pi * freq * t + 0.4)
         + 0.10 * np.sin(6.0 * np.pi * freq * t + 1.1))
    return amp * env * s


def build_plucks(rng, n_total):
    out = np.zeros((2, n_total))
    n_cycles = REPEATS
    for cyc in range(n_cycles):
        for k in range(4):
            base = cyc * CYCLE + 1.3 + k * 8.0
            t0 = base + rng.uniform(-1.3, 1.3)
            t0 = float(np.clip(t0, cyc * CYCLE + 0.7, (cyc + 1) * CYCLE - 1.2))
            bar = int((t0 % CYCLE) // BAR) % BARS
            notes = CHORDS[PROGRESSION[bar]]["notes"]
            m = notes[int(rng.integers(0, len(notes)))] + 12 * int(rng.integers(1, 2))
            f = midi_hz(m)
            pan = float(rng.uniform(-0.55, 0.55))
            amp = float(rng.uniform(0.080, 0.110))
            sig = pluck(f, 1.2, amp)
            gl = np.sqrt(0.5 * (1.0 - pan))
            gr = np.sqrt(0.5 * (1.0 + pan))
            add_wrapped(out, int(t0 * SR), np.stack([sig * gl, sig * gr]))
            # two soft echoes, opposite side, for depth
            for e, (dt, ga) in enumerate(((0.34, 0.26), (0.68, 0.11))):
                pe = float(rng.uniform(-0.5, 0.5)) * -np.sign(pan)
                g1 = np.sqrt(0.5 * (1.0 - pe))
                g2 = np.sqrt(0.5 * (1.0 + pe))
                add_wrapped(out, int((t0 + dt) * SR),
                            np.stack([sig * g1, sig * g2]) * ga)
    return out


def build_air(rng, pad_rms):
    n = int(CYCLE * SR)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    lo, hi = 3500.0, 9500.0
    m = np.zeros_like(f)
    m[(f >= lo) & (f <= hi)] = 1.0
    a = (f >= lo * 0.6) & (f < lo)
    m[a] = 0.5 - 0.5 * np.cos(np.pi * (f[a] - lo * 0.6) / (lo * 0.4))
    b = (f > hi) & (f <= hi * 1.4)
    m[b] = 0.5 + 0.5 * np.cos(np.pi * (f[b] - hi) / (hi * 0.4))
    spec = np.fft.rfft(rng.standard_normal((2, n)), axis=1) * m[None, :]
    nz = np.fft.irfft(spec, n=n, axis=1)
    nz /= max(rms(nz), 1e-12)
    nz *= pad_rms * 10.0 ** (-40.0 / 20.0)
    tt = np.arange(n, dtype=np.float64) / SR
    lfo = 0.72 + 0.28 * (0.5 - 0.5 * np.cos(2.0 * np.pi * tt / 16.0))
    nz *= lfo[None, :]
    return np.tile(nz, (1, REPEATS))


def build_bgm():
    rng = np.random.default_rng(SEED)
    n_total = int(round(TOTAL * SR))

    pad = np.tile(build_pad_cycle(rng), (1, REPEATS))

    def fc(t):
        return 1600.0 + 320.0 * np.sin(2.0 * np.pi * t / 56.0 + 0.6) \
            + 110.0 * np.sin(2.0 * np.pi * t / 112.0 + 2.1)

    pad = tv_lowpass(pad, fc)
    pad_rms = rms(pad)

    bass = build_bass(rng, n_total)
    pl = build_plucks(rng, n_total)
    air = build_air(rng, pad_rms)

    mix = pad + bass + pl + air

    # ---- circular reverb (224 s period -> seam stays continuous) ----
    ir = make_ir(dur=2.2, rt60=2.0, dark=5000.0)
    for c in range(2):
        rev = circ_conv(mix[c], ir[c])
        mix[c] = 0.80 * mix[c] + 0.45 * rev

    mix -= mix.mean(axis=1, keepdims=True)

    target = db2lin(-18.2)
    mix *= target / max(rms(mix), 1e-12)
    cap = db2lin(-3.2)
    if peak(mix) > cap:
        mix *= cap / peak(mix)

    return mix


# --------------------------------------------------------------------------
# SFX builders
# --------------------------------------------------------------------------


def finish(x, peak_db, fade_in=0.003, fade_out=0.020):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x])
    n = x.shape[1]
    x = x - x.mean(axis=1, keepdims=True)
    fi = min(int(fade_in * SR), n // 3)
    fo = min(int(fade_out * SR), n // 3)
    if fi > 0:
        x[:, :fi] *= raised_cos(np.arange(fi) / fi)
    if fo > 0:
        x[:, -fo:] *= raised_cos(np.arange(fo)[::-1] / fo)
    p = peak(x)
    if p > 0:
        x *= db2lin(peak_db) / p
    return x


def build_whoosh_soft():
    dur = 0.82
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    chans = []
    for c, (f0, f1, seed) in enumerate(((330.0, 1500.0, 11), (360.0, 1650.0, 12))):
        nz = np.random.default_rng(SEED + seed).standard_normal(n)
        y = spectral_mask(nz, lambda tt, f0=f0, f1=f1: f0 * (f1 / f0) ** np.clip(tt / dur, 0, 1),
                          width_oct=1.15)
        low = fftconv(nz, fir_bp(75.0, 240.0, 257)) * 0.32
        chans.append(y + low)
    x = np.stack(chans)
    env = np.where(t < 0.30,
                   raised_cos(t / 0.30),
                   np.exp(-(t - 0.30) / 0.15))
    x *= env[None, :]
    return finish(x, -6.0, 0.004, 0.02)


def build_whoosh_hard():
    dur = 0.64
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    chans = []
    for c, (f0, f1, seed) in enumerate(((700.0, 5200.0, 21), (620.0, 4600.0, 22))):
        nz = np.random.default_rng(SEED + seed).standard_normal(n)
        y = spectral_mask(nz, lambda tt, f0=f0, f1=f1: f0 * (f1 / f0) ** np.clip(tt / dur, 0, 1),
                          width_oct=1.25)
        y += fftconv(nz, fir_bp(3000.0, 10000.0, 257)) * 0.25
        y += fftconv(nz, fir_bp(120.0, 400.0, 257)) * 0.30
        chans.append(y)
    x = np.stack(chans)
    env = np.where(t < 0.11, raised_cos(t / 0.11), np.exp(-(t - 0.11) / 0.13))
    x *= env[None, :]
    return finish(x, -4.5, 0.003, 0.02)


def build_impact_low():
    dur = 1.65
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    f = 42.0 + 33.0 * np.exp(-t / 0.09)
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) + 0.20 * np.sin(2.0 * ph) + 0.06 * np.sin(3.0 * ph)
    body *= raised_cos(t / 0.005) * np.exp(-t / 0.46)
    rng = np.random.default_rng(SEED + 31)
    nz = rng.standard_normal(n)
    click = fftconv(nz, fir_bp(1200.0, 7000.0, 257))
    click *= np.exp(-t / 0.010) * 0.55
    tail = fftconv(nz, fir_bp(60.0, 320.0, 257))
    tail *= np.exp(-t / 0.55) * 0.16 * (t > 0.02)
    x = body * 0.90 + click + tail
    x = np.stack([x, np.roll(x, 9)])
    rev = make_ir(dur=0.9, rt60=0.8, seed=SEED + 621, dark=3500.0)
    for c in range(2):
        x[c] += 0.18 * fftconv(x[c], rev[c])
    return finish(x, -3.2, 0.002, 0.05)


def build_impact_hit():
    dur = 1.05
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    body = (np.sin(2.0 * np.pi * 150.0 * t) * np.exp(-t / 0.075)
            + 0.55 * np.sin(2.0 * np.pi * 232.0 * t + 0.7) * np.exp(-t / 0.11))
    body *= raised_cos(t / 0.003)
    rng = np.random.default_rng(SEED + 41)
    nz = rng.standard_normal(n)
    burst = fftconv(nz, fir_bp(500.0, 3200.0, 257)) * np.exp(-t / 0.012) * 0.8
    x = body * 0.7 + burst
    x = np.stack([x, np.roll(x, 5)])
    rev = make_ir(dur=0.75, rt60=0.7, seed=SEED + 631, dark=4500.0)
    for c in range(2):
        x[c] += 0.30 * fftconv(x[c], rev[c])
    return finish(x, -3.5, 0.001, 0.04)


def build_pop():
    dur = 0.16
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    f = 480.0 + 900.0 * np.exp(-t / 0.025)
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * raised_cos(t / 0.0015) * np.exp(-t / 0.042)
    rng = np.random.default_rng(SEED + 51)
    click = fftconv(rng.standard_normal(n), fir_bp(1500.0, 6000.0, 129))
    click *= np.exp(-t / 0.0035) * 0.35
    x = (x + click) * 0.9
    x = np.stack([x, np.roll(x, 3)])
    return finish(x, -7.0, 0.001, 0.015)


def build_tick():
    dur = 0.06
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    x = (np.sin(2.0 * np.pi * 3900.0 * t) * np.exp(-t / 0.010)
         + 0.55 * np.sin(2.0 * np.pi * 5900.0 * t + 0.6) * np.exp(-t / 0.007))
    x *= raised_cos(t / 0.0008)
    rng = np.random.default_rng(SEED + 61)
    x += fftconv(rng.standard_normal(n), fir_bp(4000.0, 12000.0, 129)) * np.exp(-t / 0.004) * 0.25
    x = np.stack([x, np.roll(x, 2)])
    return finish(x, -9.0, 0.0005, 0.008)


def build_riser():
    dur = 2.20
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    ramp = (t / dur) ** 2.2
    chans = []
    for c, (f0, f1, seed) in enumerate(((260.0, 5200.0, 71), (240.0, 4700.0, 72))):
        nz = np.random.default_rng(SEED + seed).standard_normal(n)
        y = spectral_mask(nz, lambda tt, f0=f0, f1=f1: f0 * (f1 / f0) ** np.clip(tt / dur, 0, 1),
                          width_oct=1.35)
        chans.append(y)
    nz = np.stack(chans)
    fsweep = 170.0 * (950.0 / 170.0) ** (t / dur)
    tone = np.sin(2.0 * np.pi * np.cumsum(fsweep) / SR)
    tone *= 0.35 * (t / dur) ** 1.4
    x = nz + tone[None, :]
    x *= ramp[None, :]
    # hard-ish exit: 25 ms fade so the cut is clean
    fo = int(0.025 * SR)
    x[:, -fo:] *= raised_cos(np.arange(fo)[::-1] / fo)
    return finish(x, -5.0, 0.01, 0.002)


def build_stamp():
    dur = 0.44
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    f = 48.0 + 55.0 * np.exp(-t / 0.035)
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    thud = np.sin(ph) * raised_cos(t / 0.002) * np.exp(-t / 0.10)
    metal = (np.sin(2.0 * np.pi * 2350.0 * t) * 0.5
             + np.sin(2.0 * np.pi * 3520.0 * t + 0.5) * 0.35
             + np.sin(2.0 * np.pi * 5210.0 * t + 1.2) * 0.22)
    metal *= np.exp(-t / 0.13) * (t > 0.001)
    rng = np.random.default_rng(SEED + 81)
    nz = fftconv(rng.standard_normal(n), fir_bp(2000.0, 6500.0, 257))
    x = thud * 0.95 + metal * 0.22 + nz * np.exp(-t / 0.008) * 0.4
    x = np.stack([x, np.roll(x, 4)])
    rev = make_ir(dur=0.5, rt60=0.45, seed=SEED + 641, dark=6000.0)
    for c in range(2):
        x[c] += 0.20 * fftconv(x[c], rev[c])
    return finish(x, -3.5, 0.001, 0.03)


def build_glitch():
    dur = 0.42
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    chans = []
    for c, seed in enumerate((91, 92)):
        rng = np.random.default_rng(SEED + seed)
        nz = rng.standard_normal(n)
        hold = 12 + 5 * c
        y = nz[(np.arange(n) // hold) * hold]
        y = np.round(y * 16.0) / 16.0
        gate = np.zeros(n)
        pos = 0
        while pos < n:
            seg = int(rng.uniform(0.012, 0.055) * SR)
            if rng.random() < 0.62:
                gate[pos:pos + seg] = 1.0
            pos += seg
        gate = fftconv(gate, fir_lp(400.0, 129))
        gate /= max(gate.max(), 1e-9)
        y = fftconv(y * gate, fir_bp(700.0, 6200.0, 257))
        chans.append(y)
    x = np.stack(chans)
    x *= np.exp(-t / 0.55)[None, :]
    return finish(x, -9.5, 0.002, 0.02)


def build_sub_drop():
    dur = 1.30
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    f = 40.0 + 42.0 * np.exp(-t / 0.24)
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    x = np.tanh(1.7 * np.sin(ph)) + 0.16 * np.sin(2.0 * ph)
    x *= raised_cos(t / 0.012) * np.exp(-t / 0.42)
    fo = int(0.05 * SR)
    x[-fo:] *= raised_cos(np.arange(fo)[::-1] / fo)
    x = np.stack([x, np.roll(x, 7)])
    return finish(x, -3.2, 0.008, 0.05)


SFX_SPEC = [
    ("whoosh-soft", build_whoosh_soft, -6.0),
    ("whoosh-hard", build_whoosh_hard, -4.5),
    ("impact-low", build_impact_low, -3.2),
    ("impact-hit", build_impact_hit, -3.5),
    ("pop", build_pop, -7.0),
    ("tick", build_tick, -9.0),
    ("riser-up", build_riser, -5.0),
    ("stamp", build_stamp, -3.5),
    ("glitch", build_glitch, -9.5),
    ("sub-drop", build_sub_drop, -3.2),
]


# --------------------------------------------------------------------------
# wav io + measurement
# --------------------------------------------------------------------------


def write_wav(path, x, rng=None):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = np.stack([x, x])
    if rng is not None:
        x = x + (rng.random(x.shape) - rng.random(x.shape)) / 32768.0 * 0.5
    q = np.clip(np.round(x * 32767.0), -32768, 32767).astype("<i2")
    inter = q.T.reshape(-1)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(inter.tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        n = wf.getnframes()
        raw = wf.readframes(n)
    data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    data = data.reshape(-1, ch).T
    return data, sr, ch, sw, n


def ffmpeg_measure(path):
    cmd = [FFMPEG, "-hide_banner", "-nostats", "-i", str(path),
           "-af", "volumedetect", "-f", "null", "NUL"]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    txt = p.stderr
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", txt)
    mx = re.search(r"max_volume:\s*(-?[\d.]+) dB", txt)
    dur = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", txt)
    srinfo = re.search(r"Audio:\s*([\w]+),\s*(\d+) Hz,\s*(stereo|mono)", txt)
    out = {
        "mean_volume": float(mean.group(1)) if mean else None,
        "max_volume": float(mx.group(1)) if mx else None,
        "sample_rate": int(srinfo.group(2)) if srinfo else None,
        "channels": 1 if (srinfo and srinfo.group(3) == "mono") else (2 if srinfo else None),
        "codec": srinfo.group(1) if srinfo else None,
        "duration": (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))) if dur else None,
    }
    return out


def octave_bands(x, sr=SR):
    X = np.fft.rfft(x * np.hanning(x.size))
    p = np.abs(X) ** 2
    f = np.fft.rfftfreq(x.size, 1.0 / sr)
    edges = [20, 60, 120, 250, 500, 1000, 2000, 4000, 8000, 16000, 24000]
    tot = max(p[(f >= 20) & (f < 24000)].sum(), 1e-20)
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        e = p[(f >= a) & (f < b)].sum() / tot
        out.append(10.0 * np.log10(max(e, 1e-12)))
    return out


def log_peaks(x, sr=SR, nbands=120):
    X = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    f = np.fft.rfftfreq(x.size, 1.0 / sr)
    edges = np.geomspace(40.0, 16000.0, nbands + 1)
    vals = np.zeros(nbands)
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        m = (f >= a) & (f < b)
        vals[i] = X[m].max() if np.any(m) else 0.0
    db = 20.0 * np.log10(np.maximum(vals, 1e-12))
    db -= db.max()
    peaks = [(float(edges[i]), float(db[i])) for i in range(1, nbands - 1)
             if db[i] > db[i - 1] and db[i] >= db[i + 1] and db[i] > -35.0]
    peaks.sort(key=lambda kv: -kv[1])
    return peaks, db


def analyse(path, loop=False):
    data, sr, ch, sw, n = read_wav(path)
    mono = data.mean(axis=0)
    info = {
        "sr": sr, "ch": ch, "bits": sw * 8, "frames": n,
        "dur": n / sr, "peak": peak(data), "rms": rms(data),
        "peak_db": lin2db(peak(data)), "rms_db": lin2db(rms(data)),
        "dc": float(np.max(np.abs(data.mean(axis=1)))),
    }
    seg = mono[int(2 * sr):int(6 * sr)] if n > 6 * sr else mono
    info["bands"] = octave_bands(seg)
    peaks, _ = log_peaks(seg)
    info["peaks"] = peaks[:6]
    info["npeaks"] = len(peaks)
    if ch == 2:
        mid = (data[0] + data[1]) * 0.5
        side = (data[0] - data[1]) * 0.5
        info["mid_rms"] = rms(mid)
        info["side_rms"] = rms(side)
        info["width_db"] = lin2db(rms(side) / max(rms(mid), 1e-12))
        c = np.corrcoef(data[0], data[1])[0, 1]
        info["corr"] = float(c)
    if loop:
        d = np.abs(np.diff(data, axis=1))
        seam = float(np.max(np.abs(data[:, 0] - data[:, -1])))
        med = float(np.median(d))
        info["seam_ratio_db"] = 20.0 * np.log10(max(seam, 1e-12) / max(med, 1e-12))
        # per-second rms min/max to prove there is no dead air
        step = sr
        segs = [rms(data[:, i:i + step]) for i in range(0, n - step, step)]
        info["sec_rms_min"] = lin2db(min(segs))
        info["sec_rms_max"] = lin2db(max(segs))
    return info


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def fmt(v, nd=1):
    return "None" if v is None else f"{v:.{nd}f}"


def main():
    only = "all"
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]

    AUDIO.mkdir(parents=True, exist_ok=True)
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    SFX_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "project": "两份开源项目声明背后的授权与署名争议 — procedural score",
        "generated_by": "v2/tools/make_audio.py",
        "sample_rate": SR,
        "bit_depth": 16,
        "channels": 2,
        "bgm": [],
        "sfx": [],
    }

    report = []

    if only in ("all", "bgm"):
        print("[bgm] synthesizing %.1f s ..." % TOTAL)
        mix = build_bgm()
        rng = np.random.default_rng(SEED + 999)
        bed = BGM_DIR / "bed-a.wav"
        write_wav(bed, mix, rng)
        info = analyse(bed, loop=True)
        ff = ffmpeg_measure(bed)
        manifest["bgm"].append({
            "file": "bgm/bed-a.wav",
            "dur": round(info["dur"], 3),
            "peak_dbfs": ff["max_volume"],
            "rms_dbfs": ff["mean_volume"],
        })
        manifest["bgm_meta"] = {
            "key": "A minor",
            "bpm": BPM,
            "bar_seconds": BAR,
            "bars": BARS,
            "cycle_seconds": CYCLE,
            "cycles": REPEATS,
            "progression": PROGRESSION,
            "loopable": True,
            "loop_technique": ("all layers rendered on a 224 s ring (pad tails, "
                               "bass, plucks, air noise and a circular FFT reverb), "
                               "so the file end continues the file start"),
            "layers": ["pad (4 voices, 12-harmonic additive wavetable, +-3-6 cent detune, TV lowpass 1.17-2.03 kHz)",
                       "sub pulse on each downbeat (chord root 41-73 Hz)",
                       "sparse plucks every ~8 s (chord tones, 2 echoes)",
                       "filtered noise air at -40 dB"],
            "reverb": "synthetic 2.2 s IR, dry 0.80 / wet 0.45 (~24% wet energy), applied circularly",
        }
        report.append(("BGM bed-a", info, ff))

    if only in ("all", "sfx"):
        for si, (name, fn, target) in enumerate(SFX_SPEC):
            print("[sfx] %s ..." % name)
            x = fn()
            p = peak(x)
            print("      pre-write peak %.2f dB (target %.1f)" % (lin2db(p), target))
            path = SFX_DIR / (name + ".wav")
            write_wav(path, x, np.random.default_rng(SEED + 100 + si))
            info = analyse(path)
            ff = ffmpeg_measure(path)
            manifest["sfx"].append({
                "name": name,
                "file": "sfx/%s.wav" % name,
                "dur": round(info["dur"], 3),
                "peak_dbfs": ff["max_volume"],
                "rms_dbfs": ff["mean_volume"],
            })
            report.append((name, info, ff))

    if only == "all":
        (AUDIO / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\n[manifest] written -> %s" % (AUDIO / "manifest.json"))

    print("\n%-13s %7s %6s %3s %8s %8s %8s %7s %8s" %
          ("file", "dur_s", "sr", "ch", "peak_f", "rms_f", "dc", "width", "seam"))
    for name, info, ff in report:
        print("%-13s %7.2f %6d %3d %8.2f %8.2f %8.2e %7s %8s" % (
            name, info["dur"], info["sr"], info["ch"], info["peak_db"],
            info["rms_db"], info["dc"],
            fmt(info.get("width_db"), 1), fmt(info.get("seam_ratio_db"), 1)))
    print("\n%-13s %8s %8s | %s" % ("file", "ff_peak", "ff_mean", "octave bands dB (63/125/250/500/1k/2k/4k/8k)"))
    for name, info, ff in report:
        b = info["bands"]
        print("%-13s %8s %8s | %s" % (
            name, fmt(ff["max_volume"]), fmt(ff["mean_volume"]),
            " ".join("%5.1f" % v for v in (b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8]))))
    print("\n%-13s %6s  top spectral peaks (Hz / dB rel max)" % ("file", "#pk"))
    for name, info, ff in report:
        ps = ", ".join("%.0f@%.0f" % (f, d) for f, d in info["peaks"])
        print("%-13s %6d  %s" % (name, info["npeaks"], ps))

    if only in ("all", "bgm"):
        b = manifest["bgm"][0]
        print("\n[check] bgm %.3f s, ffmpeg peak %s dBFS, mean %s dBFS" %
              (b["dur"], fmt(b["peak_dbfs"]), fmt(b["rms_dbfs"])))
        print("[check] bgm duration in 200-240 s: %s" % (200.0 <= b["dur"] <= 240.0))
        print("[check] bgm peak <= -3 dBFS: %s" % (b["peak_dbfs"] <= -3.0))
    print("\ndone.")


if __name__ == "__main__":
    main()
