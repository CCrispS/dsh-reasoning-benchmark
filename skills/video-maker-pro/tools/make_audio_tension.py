# -*- coding: utf-8 -*-
"""make_audio2.py -- procedural score + SFX for a dark documentary-style video.

Pure numpy + the stdlib wave module.  No scipy, no librosa, no external
binaries, no downloads.  Every sound is synthesised from oscillators, shaped
noise (FIR low/high/band pass), exponential envelopes and a small Schroeder
reverb (4 parallel combs + 2 series allpasses, rendered once into an impulse
response and applied by FFT convolution).

Outputs
  audio/bgm/bed-b.wav       ~320 s, D minor, 92 BPM, tension / interrogation bed
  audio/sfx/*.wav           8 one-shots
  audio/manifest2.json      measured metadata

All console output is ASCII only (the console codepage is GBK).
"""

import json
import math
import os
import time
import wave

import numpy as np

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
SR = 48000
SEED = 20261122
BPM = 92.0
BEAT = SR * 60.0 / BPM          # 31304.35 samples
BAR = 4.0 * BEAT                # 125217.39 samples
BARS = 123                      # integer number of bars: 320.87 s
NSAMP = int(round(BARS * BAR))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIR_BGM = os.path.join(ROOT, "audio", "bgm")
DIR_SFX = os.path.join(ROOT, "audio", "sfx")

PEAK_CEIL_DB = -3.2             # every delivered file stays below -3 dBFS
BED_RMS_DB = -18.0

T0 = time.time()


def log(msg):
    print("[%6.1fs] %s" % (time.time() - T0, msg))


# --------------------------------------------------------------------------
# small numeric helpers
# --------------------------------------------------------------------------
def tarr(n):
    return np.arange(n, dtype=np.float64) / SR


def measure(st):
    """peak and rms of an (n,) or (n,2) float array."""
    a = np.asarray(st, dtype=np.float64)
    if a.size == 0:
        return 0.0, 0.0
    peak = float(np.max(np.abs(a)))
    rms = float(np.sqrt(np.mean(a * a)))
    return peak, rms


def dbfs(x):
    return 20.0 * math.log10(max(float(x), 1e-12))


def mix_in(dst, sig, start, gain=1.0):
    """add a 1-D signal into a 1-D float32 buffer at sample position start."""
    if gain == 0.0 or dst.size == 0:
        return
    s = int(start)
    if s < 0:
        sig = sig[-s:]
        s = 0
    if s >= dst.size or len(sig) == 0:
        return
    e = min(dst.size, s + len(sig))
    dst[s:e] += (np.asarray(sig[: e - s], dtype=np.float64) * gain).astype(np.float32)


def place_st(st, sig, t0, gL=1.0, gR=1.0):
    """add a mono signal into an (n,2) float32 buffer at time t0 seconds."""
    n = st.shape[0]
    s = int(round(t0 * SR))
    sig = np.asarray(sig, dtype=np.float64)
    if s < 0:
        sig = sig[-s:]
        s = 0
    if s >= n or len(sig) == 0:
        return
    e = min(n, s + len(sig))
    seg = sig[: e - s]
    st[s:e, 0] += (seg * gL).astype(np.float32)
    st[s:e, 1] += (seg * gR).astype(np.float32)


# --------------------------------------------------------------------------
# FIR design + fast convolution
# --------------------------------------------------------------------------
def lp_kernel(fc, taps=4097):
    taps = int(taps) | 1
    fc = float(np.clip(fc, 5.0, SR * 0.45))
    n = np.arange(taps) - (taps - 1) // 2
    w = np.blackman(taps)
    h = 2.0 * fc / SR * np.sinc(2.0 * fc / SR * n) * w
    s = float(np.sum(h))
    if abs(s) < 1e-12:
        return np.array([1.0])
    return h / s


def hp_kernel(fc, taps=4097):
    taps = int(taps) | 1
    h = -lp_kernel(fc, taps)
    h[(taps - 1) // 2] += 1.0
    return h


def bp_kernel(f1, f2, taps=4097):
    taps = int(taps) | 1
    f1 = max(float(f1), 8.0)
    f2 = min(float(f2), SR * 0.45)
    if f2 <= f1 * 1.02:
        return np.zeros(taps)
    return lp_kernel(f2, taps) - lp_kernel(f1, taps)


def conv_add(dst, x, h, gain=1.0):
    """overlap-add convolution of x with h into dst (1-D float32)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    h = np.asarray(h, dtype=np.float64).ravel()
    n = len(x)
    m = len(h)
    if n == 0 or dst.size == 0:
        return
    if m <= 1:
        mix_in(dst, x * (h[0] if m else 1.0), 0, gain)
        return
    nfft = 1 << int(np.ceil(np.log2(max(2048, 4 * m))))
    nfft = min(nfft, 1 << 20)
    hop = nfft - m + 1
    if hop < 1:
        hop = nfft
    H = np.fft.rfft(h, nfft)
    for s in range(0, n, hop):
        seg = x[s:s + hop]
        y = np.fft.irfft(np.fft.rfft(seg, nfft) * H, nfft)
        e = min(s + nfft, dst.size)
        if e > s:
            dst[s:e] += (y[: e - s] * gain).astype(np.float32)


def filt(x, h):
    """linear-phase FIR filter for long signals, group delay compensated."""
    h = np.asarray(h, dtype=np.float64).ravel()
    n = len(x)
    out = np.zeros(n + len(h), dtype=np.float32)
    conv_add(out, x, h)
    d = (len(h) - 1) // 2
    y = np.zeros(n, dtype=np.float32)
    e = min(n, out.size - d)
    if e > 0:
        y[:e] = out[d:d + e]
    return y.astype(np.float64)


def conv_same(x, h):
    """linear-phase FIR filter, same length as x, delay compensated."""
    x = np.asarray(x, dtype=np.float64)
    h = np.asarray(h, dtype=np.float64).ravel()
    if len(x) > 300000:
        return filt(x, h)
    d = (len(h) - 1) // 2
    y = np.convolve(x, h)
    return y[d:d + len(x)]


def fft_conv(x, h):
    """full linear convolution (short/medium signals)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    h = np.asarray(h, dtype=np.float64).ravel()
    n, m = len(x), len(h)
    if n == 0 or m == 0:
        return np.zeros(0)
    L = n + m - 1
    nfft = 1 << int(np.ceil(np.log2(max(16, L))))
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:L]


# --------------------------------------------------------------------------
# Schroeder reverb: 4 damped combs + 2 allpasses -> impulse response
# --------------------------------------------------------------------------
def _comb_damped(x, D, g, damp):
    n = len(x)
    y = np.zeros(n)
    D = max(1, int(D))
    y[:min(D, n)] = x[:min(D, n)]
    a = float(np.clip(damp, 0.02, 0.95))
    K = int(np.ceil(np.log(1e-4) / np.log(a))) + 1
    kern = (1.0 - a) * a ** np.arange(K)
    ramp = a ** (np.arange(D) + 1.0)
    state = 0.0
    for s in range(D, n, D):
        e = min(s + D, n)
        prev = y[s - D:e - D]
        lp = np.convolve(prev, kern)[: len(prev)]
        lp = lp + state * ramp[: len(prev)]
        state = float(lp[-1])
        y[s:e] = x[s:e] + g * lp
    return y


def _allpass(x, D, g):
    n = len(x)
    y = np.zeros(n)
    D = max(1, int(D))
    m = min(D, n)
    y[:m] = -g * x[:m]
    for s in range(D, n, D):
        e = min(s + D, n)
        y[s:e] = -g * x[s:e] + x[s - D:e - D] + g * y[s - D:e - D]
    return y


def build_ir(rt60=2.4, seed=1, predelay=0.020, damp=0.55, spread=1.0,
             combs=(1687, 1753, 1613, 1543), aps=(245, 605), early=True):
    rng = np.random.default_rng(seed)
    n = int(SR * (rt60 * 1.02 + predelay + 0.05))
    imp = np.zeros(n)
    imp[0] = 1.0
    acc = np.zeros(n)
    for D in combs:
        D = int(D * spread)
        if D >= n:
            continue
        g = 10.0 ** (-3.0 * D / (rt60 * SR))
        acc += _comb_damped(imp, D, g, damp) * 0.5
    x = _allpass(acc, int(aps[0] * spread), 0.5)
    x = _allpass(x, int(aps[1] * spread), 0.5)
    if early:
        er = np.zeros(n)
        for i, td in enumerate((0.007, 0.011, 0.017, 0.023, 0.031, 0.043)):
            k = int(td * SR) + int(rng.integers(0, 180))
            if k < n:
                er[k] += (0.62 ** i) * (1.0 if rng.random() > 0.5 else -1.0)
        x = x + 0.6 * er
    d = int(predelay * SR)
    if d > 0:
        x = np.concatenate([np.zeros(d), x])[:n]
    fade = int(0.12 * SR)
    if fade < n:
        x[-fade:] *= np.linspace(1.0, 0.0, fade) ** 1.4
    x /= math.sqrt(float(np.sum(x * x))) + 1e-12
    return x.astype(np.float32)


def add_reverb(st, send, irL, irR, gain=1.0):
    n = st.shape[0]
    mono = 0.5 * (st[:, 0].astype(np.float64) + st[:, 1].astype(np.float64))
    x = mono * send
    vL = fft_conv(x, irL)[:n]
    vR = fft_conv(x, irR)[:n]
    st[:, 0] += (vL * gain).astype(np.float32)
    st[:, 1] += (vR * gain).astype(np.float32)
    return st


# --------------------------------------------------------------------------
# mastering helpers
# --------------------------------------------------------------------------
def soft_limit(x, thr, knee=0.72):
    a = np.abs(x)
    k = thr * knee
    over = np.maximum(a - k, 0.0)
    y = np.where(a <= k, a, k + (thr - k) * (1.0 - np.exp(-over / (thr - k))))
    return np.sign(x) * y


def fit_bed(st, rms_db=BED_RMS_DB, peak_db=PEAK_CEIL_DB + 0.2, iters=10):
    st = np.asarray(st, dtype=np.float64)
    thr = 10.0 ** (peak_db / 20.0)
    for _ in range(iters):
        pk, rms = measure(st)
        if rms <= 0:
            break
        st *= (10.0 ** (rms_db / 20.0)) / rms
        pk, rms = measure(st)
        if pk > thr:
            st = soft_limit(st, thr)
    return st


def edge_fade(st, fade_in=0.003, fade_out=0.035):
    """short raised-cosine fades so file edges never click on playback."""
    st = np.array(st, dtype=np.float64)
    n = st.shape[0]
    fi = min(int(fade_in * SR), n)
    fo = min(int(fade_out * SR), n)
    if fi > 1:
        w = (0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi))[:, None]
        st[:fi] *= w
    if fo > 1:
        w = (0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo))[:, None]
        st[n - fo:] *= w
    return st


def normalize_peak(st, peak_db=PEAK_CEIL_DB):
    st = np.asarray(st, dtype=np.float64)
    pk, _ = measure(st)
    if pk > 0:
        st = st * (10.0 ** (peak_db / 20.0) / pk)
    return st


def write_wav(path, st, peak_db=PEAK_CEIL_DB):
    st = np.asarray(st, dtype=np.float64)
    if st.ndim == 1:
        st = np.stack([st, st], axis=1)
    st = normalize_peak(st, peak_db)
    st = np.clip(st, -1.0, 1.0)
    ints = np.round(st * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(ints.tobytes())


def analyze(path):
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nf = w.getnframes()
        raw = w.readframes(nf)
    if sw != 2:
        raise RuntimeError("expected 16-bit, got %d" % sw)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    a = a.reshape(-1, ch)
    peak = float(np.max(np.abs(a))) if a.size else 0.0
    rms = float(np.sqrt(np.mean(a * a))) if a.size else 0.0
    if ch == 2:
        l = a[:, 0]
        r = a[:, 1]
        den = math.sqrt(float(np.mean(l * l)) * float(np.mean(r * r))) + 1e-12
        corr = float(np.mean(l * r)) / den
        mid = 0.5 * (l + r)
        mid_loss = dbfs(float(np.sqrt(np.mean(mid * mid)))) - dbfs(float(np.sqrt(np.mean(l * l))))
    else:
        corr = 1.0
        mid_loss = 0.0
    return dict(dur=nf / float(sr), peak_db=dbfs(peak), rms_db=dbfs(rms),
                sample_rate=sr, channels=ch, corr=corr, mid_loss=mid_loss)


# --------------------------------------------------------------------------
# instrument / texture builders
# --------------------------------------------------------------------------
def make_pulse(seed=11, f0=64.0, f1=38.0, tau=0.09):
    """short low thump: pitch-drop sine + sub + soft click."""
    n = int(0.60 * SR)
    t = tarr(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.050)
    ph = 2.0 * np.pi * np.cumsum(f) / SR
    env = np.exp(-t / tau) * np.minimum(1.0, t / 0.005)
    s = np.sin(ph) * env
    s += 0.32 * np.sin(0.5 * ph) * env
    s = conv_same(s, lp_kernel(520, 2049))
    rng = np.random.default_rng(seed)
    click = rng.standard_normal(n) * np.exp(-t / 0.0045) * np.minimum(1.0, t / 0.0015)
    click = conv_same(click, bp_kernel(120, 900, 1025))
    s += 0.22 * click
    return s / (np.max(np.abs(s)) + 1e-12)


def make_brass_hit(dur=3.1, seed=5):
    """Dm brass stab: additive saw stack whose upper harmonics die first."""
    n = int(dur * SR)
    t = tarr(n)
    bend = 2.0 ** (-26.0 * np.minimum(1.0, t / 0.11) / 1200.0)
    out = np.zeros(n)
    voices = ((73.416, 30, 1.00), (110.000, 18, 0.62), (146.832, 14, 0.50),
              (174.614, 12, 0.38), (220.000, 10, 0.30))
    for f0, nh, amp in voices:
        acc = np.zeros(n)
        for k in range(1, nh + 1):
            f = f0 * k * bend
            ph = 2.0 * np.pi * np.cumsum(f) / SR + 0.63 * k
            e = np.exp(-t / max(0.16, 1.35 / (1.0 + 0.16 * k)))
            acc += (np.sin(ph) / k) * e
        out += amp * acc
    env = np.minimum(1.0, t / 0.045) * np.exp(-t / 0.62)
    env *= (1.0 - np.exp(-t / 0.004))
    out *= env
    # breath / blat noise
    rng = np.random.default_rng(seed)
    nz = rng.standard_normal(n) * np.exp(-t / 0.10) * np.minimum(1.0, t / 0.008)
    nz = conv_same(nz, bp_kernel(180, 1600, 1025))
    out += 0.16 * nz
    # sub weight
    out += 0.30 * np.sin(2.0 * np.pi * 45.0 * t) * np.exp(-t / 0.35) * np.minimum(1.0, t / 0.010)
    out = conv_same(out, lp_kernel(2600, 2049))
    out *= 1.0 - np.minimum(1.0, np.maximum(t - (dur - 0.35), 0.0) / 0.35)
    return out / (np.max(np.abs(out)) + 1e-12)


def bell(f, dur=1.0, tau=0.30, seed=0):
    n = int(dur * SR)
    t = tarr(n)
    s = np.sin(2 * np.pi * f * t) * np.exp(-t / tau)
    s += 0.40 * np.sin(2 * np.pi * f * 2.01 * t + 0.7) * np.exp(-t / (tau * 0.55))
    s += 0.18 * np.sin(2 * np.pi * f * 2.98 * t + 1.9) * np.exp(-t / (tau * 0.35))
    s *= np.minimum(1.0, t / 0.004)
    return s


def sweep_band_noise(rng, dur, bands, sweep_exp=1.7, width=0.85, taps=2049):
    """band-bank noise sweep: fixed bands, moving gaussian crossfade."""
    n = int(dur * SR)
    u = np.clip(np.arange(n, dtype=np.float64) / n, 0.0, 1.0)
    c = (u ** sweep_exp) * (len(bands) - 1)
    x = rng.standard_normal(n)
    out = np.zeros(n)
    for i, fc in enumerate(bands):
        g = np.exp(-((c - i) ** 2) / (2.0 * width * width))
        if float(np.max(g)) < 1e-3:
            continue
        lo = bands[max(i - 1, 0)]
        hi = min(bands[min(i + 1, len(bands) - 1)] * 1.9, SR * 0.45)
        y = filt(x, bp_kernel(lo, hi, taps))
        out += y * g
    return out


def samp_env(points, n):
    """piecewise-linear envelope given (bar, value) pairs -> float32 [n]."""
    xs = np.array([p[0] for p in points], dtype=np.float64)
    ys = np.array([p[1] for p in points], dtype=np.float64)
    x = np.arange(n, dtype=np.float64) / BAR
    return np.interp(x, xs, ys).astype(np.float32)


def point_env(points, x):
    xs = np.array([p[0] for p in points], dtype=np.float64)
    ys = np.array([p[1] for p in points], dtype=np.float64)
    return float(np.interp(x, xs, ys))


# --------------------------------------------------------------------------
# BED-B
# --------------------------------------------------------------------------
def build_bed(irL, irR):
    log("bed: rendering %d samples (%.2f s, %d bars @ %.0f bpm)"
        % (NSAMP, NSAMP / SR, BARS, BPM))
    N = NSAMP
    drone = np.zeros(N, dtype=np.float32)
    pulse = np.zeros(N, dtype=np.float32)
    brass = np.zeros(N, dtype=np.float32)
    airL = np.zeros(N, dtype=np.float32)
    airR = np.zeros(N, dtype=np.float32)

    # ---------------- drone: low D, slow attack, breathing partials ----------
    t = np.arange(N, dtype=np.float64) / SR
    d = np.zeros(N)
    parts = ((36.708, 0.30), (73.416, 0.74), (110.000, 0.40),
             (146.832, 0.62), (174.614, 0.24), (220.000, 0.20),
             (293.665, 0.10))
    for i, (f, a) in enumerate(parts):
        lfo = 0.72 + 0.28 * np.sin(2 * np.pi * (0.013 + 0.008 * i) * t + 1.9 * i)
        s = np.sin(2 * np.pi * f * t + 0.7 * i) \
            + 0.55 * np.sin(2 * np.pi * f * 1.0009 * t + 1.3 * i)
        d += a * lfo * s
    d /= 4.10
    d *= np.minimum(1.0, t / 6.0) ** 1.5
    d = np.tanh(d * 1.10) / 1.10
    d *= samp_env([(0, 0.55), (6, 0.82), (16, 0.92), (40, 1.0), (64, 1.0),
                   (96, 1.06), (110, 1.0), (116, 0.9), (120, 0.6), (122, 0.3)], N)
    d *= 0.090 / (math.sqrt(float(np.mean(d * d))) + 1e-12)
    drone += d.astype(np.float32)
    del d, t
    pk, rms = measure(drone)
    log("bed: drone rms %.1f dB peak %.1f dB" % (dbfs(rms), dbfs(pk)))

    # ---------------- heartbeat / morse pulse on every beat -----------------
    p1 = make_pulse(11, 64.0, 38.0, 0.090)
    p2 = make_pulse(12, 60.0, 35.0, 0.105)
    pxs = [(0, 0.0), (4, 0.0), (10, 0.45), (18, 0.72), (32, 0.86),
           (64, 0.98), (88, 1.06), (112, 1.02), (118, 0.92), (121, 0.6), (122.5, 0.0)]
    rng = np.random.default_rng([SEED, 21])
    nbeats = BARS * 4
    for b in range(nbeats):
        bp = b / 4.0
        g = point_env(pxs, bp)
        if g <= 0.001:
            continue
        g *= 0.92 + 0.16 * rng.random()
        g *= 0.85 if (b % 4) == 0 else 1.0
        sig = p1 if (b % 2 == 0) else p2
        mix_in(pulse, sig, b * BEAT, 0.48 * g)
        # morse-like double hit on every 16th bar downbeat
        if (b % 64) == 0 and bp >= 12:
            mix_in(pulse, p1, b * BEAT + 0.115 * SR, 0.18 * g)
    pk, rms = measure(pulse)
    log("bed: pulse rms %.1f dB peak %.1f dB" % (dbfs(rms), dbfs(pk)))

    # ---------------- brass stab every 8 bars -------------------------------
    hit = make_brass_hit()
    accents = [(9, 0.30), (17, 0.38), (25, 0.44), (33, 0.50), (41, 0.56),
               (49, 0.60), (57, 0.66), (65, 0.70), (73, 0.75), (81, 0.80),
               (89, 0.86), (97, 0.90), (105, 0.96), (113, 1.0)]
    brng = np.random.default_rng([SEED, 22])
    for bar, g in accents:
        r = 1.0 + brng.uniform(-0.006, 0.006)
        idx = np.arange(int(len(hit) / r)) * r
        sig = np.interp(idx, np.arange(len(hit)), hit)
        mix_in(brass, sig, bar * BAR, g * 0.62)
    pk, rms = measure(brass)
    log("bed: brass rms %.1f dB peak %.1f dB" % (dbfs(rms), dbfs(pk)))

    # ---------------- high creek: chromatic crawl D5 -> A5 ------------------
    crng = np.random.default_rng([SEED, 23])
    steps = [(0, 0), (12, 1), (26, 2), (40, 3), (54, 4), (68, 5), (82, 6), (96, 7)]
    ar = np.arange(N, dtype=np.float32)
    semis = np.zeros(N, dtype=np.float32)
    for bar, _s in steps[1:]:
        c = bar * BAR
        w = np.clip((ar - c) / (2.2 * SR), 0.0, 1.0)
        w = w * w * (3.0 - 2.0 * w)
        semis += w
    vib = 0.09 * np.sin(2 * np.pi * 0.13 * ar / SR) + 0.04 * np.sin(2 * np.pi * 0.31 * ar / SR + 1.1)
    cents = semis + vib
    f0 = 587.330 * np.power(2.0, (cents - 3.2) / 12.0)
    f1 = 587.330 * np.power(2.0, (cents + 3.2) / 12.0)
    ph0 = 2 * np.pi * np.cumsum(f0.astype(np.float64)) / SR
    ph1 = 2 * np.pi * np.cumsum(f1.astype(np.float64)) / SR
    o0 = np.sin(ph0) + 0.22 * np.sin(2 * ph0) + 0.07 * np.sin(3 * ph0)
    o1 = np.sin(ph1) + 0.22 * np.sin(2 * ph1) + 0.07 * np.sin(3 * ph1)
    del ph0, ph1
    trem = 0.65 + 0.35 * np.sin(2 * np.pi * 0.07 * ar / SR + 0.4)
    cg = samp_env([(0, 0.0), (10, 0.30), (24, 0.45), (48, 0.58), (72, 0.70),
                   (96, 0.80), (112, 0.86), (118, 0.6), (122, 0.0)], N)
    cenv = (0.0135 * trem * cg).astype(np.float32)
    airL += (o0 * 0.78 + o1 * 0.34).astype(np.float32) * cenv
    airR += (o1 * 0.78 + o0 * 0.34).astype(np.float32) * cenv
    del o0, o1, ar

    # water droplets
    notes = (587.330, 698.456, 880.000, 1046.502, 1174.659)
    tcur = 3.0
    while tcur < NSAMP / SR - 4.0:
        f = notes[int(crng.integers(0, len(notes)))]
        b = bell(f, 1.4, 0.26 + 0.12 * crng.random(), 0)
        g = 0.011 * (0.5 + crng.random())
        pan = crng.uniform(-0.75, 0.75)
        gL = g * (1.0 - 0.5 * max(0.0, pan))
        gR = g * (1.0 + 0.5 * min(0.0, pan))
        place_st_arr(airL, airR, b, tcur, gL, gR)
        tcur += crng.uniform(2.2, 6.5)

    # ---------------- air bed: filtered noise + ticking ---------------------
    nrng = np.random.default_rng([SEED, 24])
    nz = nrng.standard_normal(N)
    nz = filt(nz, lp_kernel(700, 4097))
    ag = samp_env([(0, 0.10), (10, 0.18), (30, 0.30), (60, 0.44), (90, 0.58),
                   (110, 0.62), (118, 0.5), (122, 0.05)], N)
    amod = (0.6 + 0.4 * np.sin(2 * np.pi * 0.045 * np.arange(N) / SR) ** 2).astype(np.float32)
    airL += (nz * 0.020).astype(np.float32) * ag * amod
    del nz
    nz2 = nrng.standard_normal(N)
    nz2 = filt(nz2, lp_kernel(560, 4097))
    airR += (nz2 * 0.020).astype(np.float32) * ag * amod
    del nz2

    # faint high "room air" 2.5-8 kHz so the bed keeps presence on small speakers
    hz = nrng.standard_normal(N)
    hz = filt(hz, hp_kernel(2600, 4097))
    hz = filt(hz, lp_kernel(8200, 2049))
    hg = samp_env([(0, 0.0), (24, 0.35), (56, 0.6), (92, 0.8), (112, 0.9),
                   (118, 0.55), (122, 0.0)], N)
    airL += (hz * 0.0075).astype(np.float32) * hg * amod
    hz2 = nrng.standard_normal(N)
    hz2 = filt(hz2, hp_kernel(2400, 4097))
    hz2 = filt(hz2, lp_kernel(7600, 2049))
    airR += (hz2 * 0.0075).astype(np.float32) * hg * amod
    del hz, hz2, hg, amod, ag

    # soft 8th-note ticking in the second half
    tick = nrng.standard_normal(int(0.02 * SR)) * np.exp(-tarr(int(0.02 * SR)) / 0.0022)
    tick = conv_same(tick, bp_kernel(2400, 7200, 1025))
    tick /= np.max(np.abs(tick)) + 1e-12
    for b in range(BARS * 2):
        bar = b / 2.0
        if bar < 66 or bar > 118:
            continue
        g = 0.40 * point_env([(66, 0.0), (80, 0.6), (100, 1.0), (118, 0.6)], bar)
        if g <= 0.001:
            continue
        side = 0.5 + 0.5 * math.sin(b * 1.7)
        place_st_arr(airL, airR, tick, b * (BEAT / 2.0), g * (0.45 + 0.55 * side),
                     g * (1.0 - 0.55 * side))

    # ---------------- risers into the big stabs -----------------------------
    for (b0, b1, g) in ((33, 41, 0.5), (57, 65, 0.6), (81, 89, 0.7), (97, 113, 0.8)):
        dur = (b1 - b0) * BAR / SR
        rr = np.random.default_rng([SEED, 30 + b0])
        bands = (220.0, 320.0, 470.0, 700.0, 1050.0, 1600.0, 2400.0, 3600.0, 5400.0)
        sw = sweep_band_noise(rr, dur, bands, sweep_exp=2.1, width=0.9)
        u = np.linspace(0.0, 1.0, len(sw))
        env = (u ** 2.6) * np.minimum(1.0, (1.0 - u) / 0.02)
        sw = sw * env
        sw /= (np.max(np.abs(sw)) + 1e-12)
        mix_in(airL, sw, b0 * BAR, 0.022 * g)
        mix_in(airR, sw, b0 * BAR, 0.018 * g)
        del sw

    rl = float(np.mean(airL.astype(np.float64) ** 2))
    rr = float(np.mean(airR.astype(np.float64) ** 2))
    arms = math.sqrt(0.5 * (rl + rr)) + 1e-12
    gair = 0.030 / arms          # air bus ~ -30.5 dBFS: audible detail, under the voice
    airL *= gair
    airR *= gair
    pk, rms = measure(airL)
    log("bed: air bus rms %.1f dB peak %.1f dB (gain %.2f)" % (dbfs(rms), dbfs(pk), gair))

    # ---------------- mix + reverb ------------------------------------------
    core = np.zeros(N, dtype=np.float32)
    core += drone
    core += pulse
    core += brass
    del drone, pulse

    send = np.zeros(N, dtype=np.float32)
    send += brass * 0.55
    send += (0.5 * (airL + airR)) * 0.85
    send += core * 0.06

    verbL = np.zeros(N, dtype=np.float32)
    verbR = np.zeros(N, dtype=np.float32)
    conv_add(verbL, send, irL, 0.55)
    log("bed: reverb left done")
    conv_add(verbR, send, irR, 0.55)
    log("bed: reverb right done")
    del send

    st = np.zeros((N, 2), dtype=np.float32)
    st[:, 0] = core + airL + verbL * 0.9
    st[:, 1] = core + airR + verbR * 0.9
    del core, airL, airR, verbL, verbR, brass

    # remove DC / subsonic
    for c in range(2):
        x = st[:, c].astype(np.float64)
        x = x - np.mean(x)
        st[:, c] = filt(x, hp_kernel(20.0, 16385)).astype(np.float32)

    pk, rms = measure(st)
    log("bed: pre-master rms %.1f dB peak %.1f dB (crest %.1f dB)"
        % (dbfs(rms), dbfs(pk), dbfs(pk) - dbfs(rms)))

    # fades: 50 ms in, 300 ms out
    fi = int(0.050 * SR)
    fo = int(0.300 * SR)
    st[:fi] *= (0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi))[:, None].astype(np.float32)
    st[-fo:] *= (0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo))[:, None].astype(np.float32)

    st = fit_bed(st)
    pk, rms = measure(st)
    log("bed: mastered rms %.2f dB peak %.2f dB" % (dbfs(rms), dbfs(pk)))
    return st


def place_st_arr(bL, bR, sig, t0, gL, gR):
    n = bL.shape[0]
    s = int(round(t0 * SR))
    if s < 0:
        sig = sig[-s:]
        s = 0
    if s >= n or len(sig) == 0:
        return
    e = min(n, s + len(sig))
    seg = sig[: e - s]
    bL[s:e] += (seg * gL).astype(np.float32)
    bR[s:e] += (seg * gR).astype(np.float32)


# --------------------------------------------------------------------------
# SFX
# --------------------------------------------------------------------------
def sfx_thunder(irL, irR):
    dur = 2.6
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 101])
    t = tarr(n)
    st = np.zeros((n, 2), dtype=np.float32)
    head = np.zeros(n)

    rum = rng.standard_normal(n)
    rum = conv_same(rum, lp_kernel(70, 4097))
    rum = conv_same(rum, lp_kernel(150, 2049))
    env = np.minimum(1.0, np.maximum(t - 0.02, 0) / 0.12) * np.exp(-np.maximum(t - 0.05, 0) / 0.75)
    mod = 0.62 + 0.38 * np.sin(2 * np.pi * (2.7 * t + 0.35 * np.sin(2 * np.pi * 0.55 * t)))
    head += rum * env * mod * 2.2

    sub = np.sin(2 * np.pi * (34.0 + 6.0 * np.exp(-t / 0.25)) * t) * np.exp(-t / 0.6) * 0.9
    head += sub * np.minimum(1.0, t / 0.05)

    crack = np.zeros(n)
    k = int(0.055 * SR)
    tt = tarr(k)
    nz = rng.standard_normal(k)
    cz = conv_same(nz, bp_kernel(250, 3200, 2049))
    crack[:k] += cz * np.exp(-tt / 0.055) * np.minimum(1.0, tt / 0.0015) * 2.4
    head += crack

    # second and third rumble swells
    for t0, g in ((0.85, 0.65), (1.55, 0.42)):
        k2 = int(1.1 * SR)
        s = int(t0 * SR)
        seg = rum[s:s + k2] * np.exp(-np.arange(min(k2, n - s)) / (0.34 * SR)) * g
        head[s:s + len(seg)] += seg

    # crackles
    cl = np.zeros(n)
    cr = np.zeros(n)
    for _ in range(16):
        t0 = float(rng.uniform(0.02, 1.9))
        L = int(rng.uniform(0.015, 0.070) * SR)
        s = int(t0 * SR)
        if s + L >= n:
            continue
        tt = tarr(L)
        for buf in (cl, cr):
            nz = rng.standard_normal(L)
            nz = conv_same(nz, bp_kernel(rng.uniform(900, 2000), rng.uniform(3500, 8000), 1025))
            buf[s:s + L] += nz * np.exp(-tt / (L / SR / 3.0)) * rng.uniform(0.08, 0.30)

    st[:, 0] += (head + 0.65 * cl + 0.30 * cr).astype(np.float32)
    st[:, 1] += (head + 0.65 * cr + 0.30 * cl).astype(np.float32)
    add_reverb(st, 0.30, irL, irR, 0.55)
    st = st[:n]
    st *= (0.5 + 0.5 * np.cos(np.pi * np.clip((t - (dur - 0.25)) / 0.25, 0, 1)))[:, None]
    return st


def sfx_riser(irL, irR):
    dur = 4.5
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 102])
    t = tarr(n)
    u = np.clip(t / dur, 0, 1)

    bands = (140.0, 200.0, 300.0, 450.0, 680.0, 1000.0, 1500.0,
             2300.0, 3400.0, 5000.0, 7200.0, 10000.0)
    swL = sweep_band_noise(rng, dur, bands, sweep_exp=2.3, width=0.95)
    swR = sweep_band_noise(rng, dur, bands, sweep_exp=2.3, width=0.95)
    common = 0.60 * (swL + swR)
    side = 0.85 * (swL - swR)
    smax = np.max(np.abs(common)) + 1e-12

    fr = 70.0 * np.power(16.0, u ** 1.8)
    ph = 2 * np.pi * np.cumsum(fr) / SR
    tone = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.16 * np.sin(3 * ph)
    tone *= 0.55

    # accelerating tick train
    ticks = np.zeros(n)
    tt = 0.30
    gap = 0.26
    while tt < dur - 0.05:
        k = int(0.012 * SR)
        s = int(tt * SR)
        if s + k < n:
            x = rng.standard_normal(k) * np.exp(-tarr(k) / 0.0018)
            x = conv_same(x, bp_kernel(1800, 6500, 513))
            ticks[s:s + k] += x * 0.9
        tt += gap
        gap = max(0.022, gap * 0.955)

    env = (u ** 2.2) * np.minimum(1.0, (1.0 - u) / 0.035)
    g = int(0.004 * SR)                       # tiny Haas spread, still mono-safe
    sideS = np.zeros(n)
    if g < n:
        sideS[g:] = side[:-g]
    Lb = (0.86 * common + 0.42 * sideS) * env
    Rb = (0.86 * common - 0.42 * sideS) * env
    tmono = tone * 0.30 * env + ticks * np.minimum(1.0, u / 0.6) * 0.55
    peak = max(np.max(np.abs(Lb)), np.max(np.abs(Rb))) + 1e-12
    Lb = Lb / peak * 0.85 + tmono
    Rb = Rb / peak * 0.85 + tmono
    pk = max(np.max(np.abs(Lb)), np.max(np.abs(Rb))) + 1e-12

    st = np.zeros((n, 2), dtype=np.float32)
    st[:, 0] = (Lb / pk).astype(np.float32)
    st[:, 1] = (Rb / pk).astype(np.float32)
    add_reverb(st, 0.22, irL, irR, 0.4)
    st *= np.minimum(1.0, (1.0 - u) / 0.008)[:, None]
    return st


def sfx_heartbeat(irL, irR):
    dur = 2.0
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 103])
    st = np.zeros((n, 2), dtype=np.float32)
    mono = np.zeros(n)

    def thump(t0, f0, f1, tau, g, seed):
        m = int(0.55 * SR)
        tt = tarr(m)
        f = f1 + (f0 - f1) * np.exp(-tt / 0.045)
        ph = 2 * np.pi * np.cumsum(f) / SR
        e = np.exp(-tt / tau) * np.minimum(1.0, tt / 0.006)
        s = np.sin(ph) * e + 0.45 * np.sin(0.5 * ph) * e
        rr = np.random.default_rng(seed)
        nz = rr.standard_normal(m) * np.exp(-tt / 0.03)
        nz = conv_same(nz, lp_kernel(190, 1025))
        s = s + 0.22 * nz
        s = conv_same(s, lp_kernel(300, 2049))
        s *= 1.0 - np.minimum(1.0, np.maximum(tt - 0.45, 0) / 0.1)
        s = s / (np.max(np.abs(s)) + 1e-12)
        mix_in(mono, s, t0 * SR, g)

    for cyc, (t0, gg) in enumerate(((0.02, 1.0), (1.02, 0.94))):
        j = rng.uniform(0.0, 0.012)
        thump(t0 + j, 66.0, 37.0, 0.17, gg, 300 + cyc)
        thump(t0 + 0.315 + j * 0.6, 72.0, 44.0, 0.105, 0.62 * gg, 310 + cyc)

    mono = conv_same(mono, hp_kernel(28.0, 4097))
    st[:, 0] += mono.astype(np.float32)
    st[:, 1] += mono.astype(np.float32)
    add_reverb(st, 0.10, irL, irR, 0.25)
    st *= np.minimum(1.0, (dur - tarr(n)) / 0.06)[:, None]
    return st


def sfx_tick(irL, irR):
    dur = 1.0
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 104])
    tock = np.zeros(int(0.06 * SR))
    tt = tarr(len(tock))
    x = rng.standard_normal(len(tock)) * np.exp(-tt / 0.0022) * np.minimum(1.0, tt / 0.0006)
    x = conv_same(x, bp_kernel(1200, 9000, 1025))
    x /= np.max(np.abs(x)) + 1e-12
    ring = np.sin(2 * np.pi * 3150 * tt) * np.exp(-tt / 0.010)
    ring += 0.55 * np.sin(2 * np.pi * 4700 * tt + 1.0) * np.exp(-tt / 0.007)
    body = np.sin(2 * np.pi * 780 * tt) * np.exp(-tt / 0.006) * 0.5
    tock = x * 0.9 + ring * 0.45 + body * 0.4
    tock /= np.max(np.abs(tock)) + 1e-12

    st = np.zeros((n, 2), dtype=np.float32)
    for k in range(8):
        t0 = k * 0.125
        g = 1.0 if (k % 4 == 0) else (0.66 if (k % 2 == 0) else 0.5)
        pan = 0.15 * ((k % 3) - 1)
        place_st(st, tock, t0, g * (1.0 - pan), g * (1.0 + pan))
    add_reverb(st, 0.10, irL, irR, 0.3)
    st *= np.minimum(1.0, (dur - tarr(n)) / 0.03)[:, None]
    return st


def sfx_whoosh(irL, irR):
    dur = 1.2
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 105])
    t = tarr(n)
    u = np.clip(t / dur, 0, 1)
    bands = (120.0, 180.0, 280.0, 430.0, 660.0, 1000.0, 1500.0, 2300.0,
             3400.0, 5000.0, 7400.0, 10500.0)
    swL = sweep_band_noise(rng, dur, bands, sweep_exp=1.9, width=0.9)
    swR = sweep_band_noise(rng, dur, bands, sweep_exp=1.9, width=0.9)
    common = 0.85 * (swL + swR)
    side = 0.32 * (swL - swR)
    L = common + side
    R = common - side
    low = rng.standard_normal(n)
    low = conv_same(low, lp_kernel(90, 2049))
    low = low * np.exp(-np.maximum(t - 0.1, 0) / 0.5)
    env = (u ** 1.5) * np.minimum(1.0, (1.0 - u) / 0.10) ** 1.2
    L = L * env + low * 0.9
    R = R * env + low * 0.9
    st = np.stack([L, R], axis=1).astype(np.float32)
    add_reverb(st, 0.18, irL, irR, 0.35)
    return st


def sfx_ding(irL, irR):
    dur = 0.9
    n = int(dur * SR)
    t = tarr(n)
    f0 = 740.0
    parts = ((1.0, 1.00, 0.55), (1.41421356, 0.70, 0.42), (2.76, 0.40, 0.24),
             (4.07, 0.26, 0.15), (5.42, 0.16, 0.10))
    st = np.zeros((n, 2), dtype=np.float32)
    L = np.zeros(n)
    R = np.zeros(n)
    mono = np.zeros(n)
    shL = np.zeros(n)
    shR = np.zeros(n)
    for i, (ratio, amp, tau) in enumerate(parts):
        f = f0 * ratio
        e = amp * np.exp(-t / tau)
        p = 2 * np.pi * f * t + i * 1.3
        mono += np.sin(p) * e
        if i >= 1:
            shL += np.sin(p * (1.0 + 0.0007) + 0.30) * e
            shR += np.sin(p * (1.0 - 0.0007) - 0.30) * e
    L = mono + 0.26 * shL
    R = mono + 0.26 * shR
    # attack click
    rng = np.random.default_rng([SEED, 106])
    k = int(0.006 * SR)
    cl = rng.standard_normal(k) * np.exp(-tarr(k) / 0.0012)
    cl = conv_same(cl, bp_kernel(1500, 9000, 513))
    L[:k] += cl * 0.6
    R[:k] += cl * 0.6
    st[:, 0] += L.astype(np.float32)
    st[:, 1] += R.astype(np.float32)
    st *= np.minimum(1.0, t / 0.0008)[:, None]
    add_reverb(st, 0.32, irL, irR, 0.6)
    st *= np.minimum(1.0, (dur - t) / 0.12)[:, None]
    return st


def sfx_typewriter(irL, irR):
    dur = 1.4
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 107])
    st = np.zeros((n, 2), dtype=np.float32)

    def key(seed):
        m = int(0.28 * SR)
        tt = tarr(m)
        rr = np.random.default_rng(seed)
        nz = rr.standard_normal(m) * np.exp(-tt / 0.0035) * np.minimum(1.0, tt / 0.0008)
        nz = conv_same(nz, bp_kernel(700, 5200, 1025))
        nz /= np.max(np.abs(nz)) + 1e-12
        res = np.sin(2 * np.pi * rr.uniform(1800, 2900) * tt) * np.exp(-tt / 0.030)
        thud = np.sin(2 * np.pi * (150.0 + 60 * np.exp(-tt / 0.01)) * tt) * np.exp(-tt / 0.028)
        s = nz * 0.9 + res * 0.4 + thud * 0.55
        s = conv_same(s, lp_kernel(7000, 1025))
        s *= 1.0 - np.minimum(1.0, np.maximum(tt - 0.20, 0) / 0.06)
        return s / (np.max(np.abs(s)) + 1e-12)

    times = [0.05, 0.235, 0.38, 0.585, 0.72, 0.905, 1.03]
    for i, t0 in enumerate(times):
        s = key(400 + i)
        g = 0.55 + 0.45 * rng.random()
        pan = rng.uniform(-0.35, 0.35)
        place_st(st, s, t0 + rng.uniform(-0.012, 0.012), g * (1 - pan), g * (1 + pan))

    # carriage bell
    m = int(0.35 * SR)
    tt = tarr(m)
    bg = (np.sin(2 * np.pi * 2093.0 * tt) + 0.4 * np.sin(2 * np.pi * 4186.0 * tt)) \
        * np.exp(-tt / 0.12) * np.minimum(1.0, tt / 0.002)
    place_st(st, bg, 1.135, 0.22, 0.26)

    st *= np.minimum(1.0, tarr(n) / 0.002)[:, None]
    add_reverb(st, 0.16, irL, irR, 0.35)
    st *= np.minimum(1.0, (dur - tarr(n)) / 0.08)[:, None]
    return st


def sfx_glitch(irL, irR):
    dur = 0.8
    n = int(dur * SR)
    rng = np.random.default_rng([SEED, 108])
    L = np.zeros(n)
    R = np.zeros(n)
    cur = 0
    while cur < n:
        gl = int(rng.uniform(0.018, 0.075) * SR)
        gl = max(32, min(gl, n - cur))
        kind = int(rng.integers(0, 5))
        m = gl
        tt = tarr(m)
        if kind == 0:
            hold = int(rng.integers(6, 70))
            x = rng.standard_normal(m)
            idx = np.minimum((np.arange(m) // hold) * hold, m - 1)
            s = np.round(x[idx] * 4.0) / 4.0
        elif kind == 1:
            f = rng.uniform(180.0, 2600.0)
            s = np.sign(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6.0)))
            s = np.round(s * 3.0) / 3.0
        elif kind == 2:
            f = rng.uniform(90.0, 1100.0)
            s = np.sin(2 * np.pi * f * tt * (1.0 + 0.6 * np.sin(2 * np.pi * 9 * tt)))
            s = np.round(s * 3.0) / 3.0
        elif kind == 3:
            s = np.zeros(m)
        else:
            x = rng.standard_normal(m)
            s = np.round(x * 2.0) / 2.0
        e = np.ones(m)
        e[:min(48, m)] = np.linspace(0, 1, min(48, m))
        e[-min(96, m):] *= np.linspace(1, 0, min(96, m))
        s = s * e * rng.uniform(0.15, 1.0)
        shake = rng.uniform(-0.4, 0.4)
        L[cur:cur + m] += s * (1.0 - shake)
        R[cur:cur + m] += s * (1.0 + shake)
        gap = int(rng.uniform(0.0, 0.055) * SR * float(rng.random())) if rng.random() < 0.75 else 0
        cur += m + gap
    # stutter repeats of a grain
    for _ in range(4):
        g0 = int(rng.integers(0, n - int(0.05 * SR)))
        glen = int(rng.uniform(0.02, 0.05) * SR)
        grain = L[g0:g0 + glen].copy()
        for r in range(int(rng.integers(2, 5))):
            p = g0 + r * glen
            if p + glen < n:
                L[p:p + glen] += grain * 0.8
                R[p:p + glen] += grain * 0.7
    # clicks
    for _ in range(6):
        p = int(rng.integers(0, n - 200))
        L[p:p + 40] += 0.8 * (1 if rng.random() > 0.5 else -1)
        R[p:p + 40] += 0.8 * (1 if rng.random() > 0.5 else -1)
    st = np.stack([L, R], axis=1).astype(np.float32)
    st = np.clip(st * 0.6, -1.0, 1.0)
    add_reverb(st, 0.10, irL, irR, 0.2)
    an = np.abs(st)
    st = np.tanh(st * 2.2) / math.tanh(2.2)
    st *= np.minimum(1.0, (dur - tarr(n)) / 0.05)[:, None]
    return st


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    os.makedirs(DIR_BGM, exist_ok=True)
    os.makedirs(DIR_SFX, exist_ok=True)
    log("building reverb impulse responses")
    irL = build_ir(rt60=2.6, seed=[SEED, 1], predelay=0.020, damp=0.55, spread=1.0)
    irR = build_ir(rt60=2.6, seed=[SEED, 2], predelay=0.024, damp=0.55, spread=1.047)
    log("IR: left %d taps, right %d taps" % (len(irL), len(irR)))

    files = []

    path = os.path.join(DIR_BGM, "bed-b.wav")
    st = build_bed(irL, irR)
    write_wav(path, st, PEAK_CEIL_DB)
    del st
    files.append(("bed-b.wav", "bgm", path))
    log("bed written: %s" % path)

    sfx = [("thunder.wav", sfx_thunder), ("riser-long.wav", sfx_riser),
           ("heartbeat.wav", sfx_heartbeat), ("tick-fast.wav", sfx_tick),
           ("whoosh-mega.wav", sfx_whoosh), ("question-ding.wav", sfx_ding),
           ("typewriter.wav", sfx_typewriter), ("glitch-burst.wav", sfx_glitch)]
    for name, fn in sfx:
        t1 = time.time()
        s = fn(irL, irR)
        s = edge_fade(s, 0.003, 0.035)
        p = os.path.join(DIR_SFX, name)
        write_wav(p, s, PEAK_CEIL_DB)
        del s
        files.append((name, "sfx", p))
        log("sfx %-18s %.2fs render" % (name, time.time() - t1))

    # ------------- measure everything back from disk -----------------------
    entries = []
    print("")
    print("%-18s %6s %9s %9s %9s" % ("FILE", "DUR", "PEAK_dB", "RMS_dB", "CH/SR"))
    for name, kind, path in files:
        m = analyze(path)
        entries.append(dict(name=name, kind=kind, dur=round(m["dur"], 3),
                            peak_db=round(m["peak_db"], 2),
                            rms_db=round(m["rms_db"], 2),
                            sample_rate=m["sample_rate"],
                            channels=m["channels"],
                            lr_corr=round(m["corr"], 3),
                            mono_loss_db=round(m["mid_loss"], 2),
                            path="audio/%s/%s" % ("bgm" if kind == "bgm" else "sfx", name)))
        print("%-18s %6.2f %9.2f %9.2f %5d/%d" %
              (name, m["dur"], m["peak_db"], m["rms_db"], m["channels"], m["sample_rate"]))
        print("    L/R corr %.3f   mid-sum level delta %.2f dB" % (m["corr"], m["mid_loss"]))

    manifest = dict(
        tool="tools/make_audio2.py",
        generator="numpy procedural synthesis (no scipy / no external binaries)",
        seed=SEED,
        sample_rate=SR,
        channels=2,
        bit_depth=16,
        peak_ceiling_db=-3.0,
        bed_b=dict(key="D minor", bpm=BPM, bars=BARS, time_signature="4/4",
                   loop="50 ms fade-in, 300 ms fade-out, integer bars"),
        files=entries,
    )
    mpath = os.path.join(ROOT, "audio", "manifest2.json")
    with open(mpath, "w", encoding="ascii") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=True)
    log("manifest written: %s" % mpath)

    print("")
    ok = True
    for e in entries:
        if e["peak_db"] > -3.0 + 1e-6:
            print("FAIL peak too hot:", e["name"], e["peak_db"])
            ok = False
        if e["sample_rate"] != SR or e["channels"] != 2:
            print("FAIL format:", e["name"])
            ok = False
    bed = [e for e in entries if e["kind"] == "bgm"][0]
    if bed["dur"] < 300.0:
        print("FAIL bed too short")
        ok = False
    print("CHECKS:", "PASS" if ok else "FAIL")
    log("done")


if __name__ == "__main__":
    main()
