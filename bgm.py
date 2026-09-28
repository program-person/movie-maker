import sys, wave
import numpy as np

SR = 44100
BPM = 88
BEAT = 60 / BPM
BAR = BEAT * 4

def midi(n): return 440.0 * 2 ** ((n - 69) / 12)

# Cmaj7 - G - Am7 - Fmaj7（1小節ずつ）
CHORDS = [[60, 64, 67, 71], [55, 59, 62, 67], [57, 60, 64, 67], [53, 57, 60, 64]]
BASS = [36, 43, 45, 41]

def env(n, a, r):
    e = np.ones(n)
    na, nr = min(int(a * SR), n), min(int(r * SR), n)   # 区間が短いときは頭打ち
    if na: e[:na] = np.linspace(0, 1, na)
    if nr: e[-nr:] *= np.linspace(1, 0, nr)
    return e

def make(total):
    n = int(total * SR)
    L = np.zeros(n); R = np.zeros(n)
    rng = np.random.default_rng(0)
    bar_i = 0
    t0 = 0.0
    while t0 < total:
        ch, bs = CHORDS[bar_i % 4], BASS[bar_i % 4]
        s = int(t0 * SR); m = min(int(BAR * SR), n - s)
        if m <= 0: break
        t = np.arange(m) / SR
        # パッド（少しデチューンして左右に広げる）
        pad_l = sum(np.sin(2 * np.pi * midi(k) * 0.998 * t) for k in ch)
        pad_r = sum(np.sin(2 * np.pi * midi(k) * 1.002 * t) for k in ch)
        e = env(m, 0.4, 0.5)
        L[s:s + m] += 0.035 * pad_l * e; R[s:s + m] += 0.035 * pad_r * e
        # ベース（1拍目と3拍目）
        for b in (0, 2):
            bs0 = s + int(b * BEAT * SR); bm = min(int(2 * BEAT * SR), n - bs0)
            if bm <= 0: continue
            tt = np.arange(bm) / SR
            v = 0.12 * np.sin(2 * np.pi * midi(bs) * tt) * np.exp(-tt * 1.8)
            L[bs0:bs0 + bm] += v; R[bs0:bs0 + bm] += v
        # アルペジオ（8分音符、柔らかいプラック）
        pattern = [0, 1, 2, 3, 2, 1, 2, 3]
        for j, p in enumerate(pattern):
            ns = s + int(j * BEAT / 2 * SR); nm = min(int(0.6 * SR), n - ns)
            if nm <= 0: continue
            tt = np.arange(nm) / SR
            f = midi(ch[p] + 12)
            v = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 6) * 0.05
            pan = 0.35 + 0.3 * (p / 3)
            L[ns:ns + nm] += v * (1 - pan); R[ns:ns + nm] += v * pan
        # 軽いキック（1・3拍）とハイハット（裏拍）
        for b in range(4):
            ks = s + int(b * BEAT * SR)
            if b in (0, 2):
                km = min(int(0.25 * SR), n - ks)
                if km > 0:
                    tt = np.arange(km) / SR
                    k = 0.12 * np.sin(2 * np.pi * (50 + 60 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 18)
                    L[ks:ks + km] += k; R[ks:ks + km] += k
            hs = ks + int(BEAT / 2 * SR); hm = min(int(0.05 * SR), n - hs)
            if hm > 0:
                h = rng.standard_normal(hm) * np.exp(-np.arange(hm) / SR * 90) * 0.015
                h = np.diff(np.concatenate([[0], h]))  # 簡易ハイパス
                L[hs:hs + hm] += h; R[hs:hs + hm] += h
        t0 += BAR; bar_i += 1
    # 全体のフェードイン・アウト
    fi, fo = min(int(1.5 * SR), n // 2), min(int(3.0 * SR), n // 2)
    for ch_ in (L, R):
        ch_[:fi] *= np.linspace(0, 1, fi); ch_[-fo:] *= np.linspace(1, 0, fo)
    st = np.stack([L, R], axis=1)
    st /= max(1e-9, np.abs(st).max()) / 0.9
    return (st * 32767).astype(np.int16)

if __name__ == "__main__":
    total, out = float(sys.argv[1]), sys.argv[2]
    data = make(total)
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes())
