"""Analytical sanity checks for the generated bed + sfx (read-only, prints ASCII)."""
import os
import wave
import json
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(BASE, "audio")
SR = 48000


def load(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        ch = w.getnchannels()
        sr = w.getframerate()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return x.reshape(-1, ch), sr


def db(v):
    return 20.0 * np.log10(max(abs(v), 1e-12))


def band_energy(x, sr, lo, hi):
    if len(x) < 4096:
        return 0.0
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    m = (f >= lo) & (f < hi)
    return float(np.sum(spec[m] ** 2) / (np.sum(spec ** 2) + 1e-12))


def centroid(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    return float(np.sum(f * spec) / (np.sum(spec) + 1e-12))


print("=== bed-b structure ===")
b, sr = load(os.path.join(AUD, "bgm", "bed-b.wav"))
assert sr == 48000 and b.shape[1] == 2
mono = b.mean(axis=1)
dur = len(mono) / sr
print("dur %.2f s  samples %d" % (dur, len(mono)))
print("dc %.5f  first50ms peak %.1f dB  last300ms peak %.1f dB"
      % (mono.mean(), db(np.max(np.abs(mono[:2400]))), db(np.max(np.abs(mono[-14400:])))))
print("head 5 samples", np.round(mono[:5] * 1e4, 2).tolist())

win = 4 * sr
rows = []
for i in range(0, len(mono) - win, win):
    seg = mono[i:i + win]
    rows.append((i / sr, db(np.sqrt(np.mean(seg ** 2))), centroid(seg, sr),
                 band_energy(seg, sr, 20, 120), band_energy(seg, sr, 120, 500),
                 band_energy(seg, sr, 500, 2000), band_energy(seg, sr, 2000, 12000)))
print(" t     rms    cent   <120Hz  120-500  500-2k  2k-12k")
for r in rows[::4]:
    print("%5.0f %7.1f %6.0f   %.3f   %.3f   %.3f   %.4f" % r)

# beat grid: envelope autocorrelation around 92 bpm (0.652 s)
env = np.abs(mono)
env = env.reshape(-1)[: len(env) // 480 * 480].reshape(-1, 480).mean(axis=1)  # 100 Hz
env = env - env.mean()
ac = np.correlate(env[: len(env) // 2], env[: len(env) // 2], mode="full")[len(env) // 2 - 1:]
ac /= ac[0] + 1e-12
bpm_period = int(round(0.65217 * 100))
print("autocorr at 1 beat (%.2f s): %.3f   at 2 beats: %.3f   at 0.5 beat: %.3f"
      % (0.65217, ac[bpm_period], ac[2 * bpm_period], ac[bpm_period // 2]))
lags = np.argsort(ac[40:200])[::-1][:6] + 40
print("top env lags (s):", [round(l / 100.0, 3) for l in lags])

# stereo width
L, R = b[:, 0], b[:, 1]
mid = (L + R) / 2
sd = (L - R) / 2
print("side/mid energy %.1f dB" % (10 * np.log10((np.mean(sd ** 2) + 1e-15) / (np.mean(mid ** 2) + 1e-15))))

print()
print("=== sfx ===")
for name in ("thunder", "riser-long", "heartbeat", "tick-fast", "whoosh-mega",
             "question-ding", "typewriter", "glitch-burst"):
    p = os.path.join(AUD, "sfx", name + ".wav")
    x, sr = load(p)
    m = x.mean(axis=1)
    d = len(m) / sr
    # envelope segments (50 ms)
    seg = int(0.05 * sr)
    ne = len(m) // seg
    e = np.array([db(np.sqrt(np.mean(m[i * seg:(i + 1) * seg] ** 2))) for i in range(ne)])
    print("%-14s dur %.2f  peak %6.1f  rms %6.1f  cent %5.0f  low%% %.2f" %
          (name, d, db(np.max(np.abs(m))), db(np.sqrt(np.mean(m ** 2))),
           centroid(m, sr), band_energy(m, sr, 0, 120)))
    print("   50ms env:", " ".join("%.0f" % v for v in e))
    if name in ("tick-fast", "heartbeat"):
        thr = e.max() - 12
        hits = [i for i in range(1, ne - 1) if e[i] > e[i - 1] and e[i] >= e[i + 1] and e[i] > thr]
        print("   onset peaks at (s):", [round(h * 0.05, 2) for h in hits])
    if name == "riser-long":
        q = len(m) // 4
        print("   centroid quarters: %.0f %.0f %.0f %.0f" %
              tuple(centroid(m[i * q:(i + 1) * q], sr) for i in range(4)))
    if name == "whoosh-mega":
        q = len(m) // 4
        print("   centroid quarters: %.0f %.0f %.0f %.0f" %
              tuple(centroid(m[i * q:(i + 1) * q], sr) for i in range(4)))
    print("   edge start %.1f dB end %.1f dB" % (db(np.max(np.abs(m[:480]))),
                                                 db(np.max(np.abs(m[-480:])))))

print()
man = json.load(open(os.path.join(AUD, "manifest2.json"), "r", encoding="utf-8"))
print("manifest files:", len(man["files"]) if isinstance(man, dict) else len(man))
print(json.dumps(man, ensure_ascii=True, indent=1)[:1600])
