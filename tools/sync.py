#!/usr/bin/env python3
"""sync.py - line up a separately recorded audio file (lav mic, wireless mic, field recorder) with the video takes.

Finds where each take's own (camera) sound sits inside the long recording with GCC-PHAT cross-correlation at several
points of the take, which also measures clock drift between the two devices. Then writes the recorder's audio cut to
the take, tempo-corrected if the clocks drift: 48 kHz mono 24-bit WAV of exactly the take's length, so take time ==
audio time. plan.py and render.py use work/NAME.lav.wav automatically when it exists (else the camera's own audio).

Usage: sync.py RECORDING.WAV --take NAME=TAKE.MOV [--take NAME2=TAKE2.MOV ...] [--outdir work] [--anchors 5] [--win 20]
Writes OUTDIR/NAME.lav.wav and prints one line per take: offset into the recording, drift, confidence.
Several recordings (the recorder splits files, or two sessions)? Run it once per recording with the takes it covers.
Confidence: the matches in testing scored 70-200; under 15 means the take is probably not in this recording.
The camera needs some sound of its own (its built-in mic is enough) to sync on.
"""
import argparse
from pathlib import Path

import numpy as np

from common import av_offset, pcm, run
from probe import probe

SR = 8000


def peak(RF, n, nref, sig):
    """GCC-PHAT: where does `sig` start inside the reference? -> (seconds, confidence)."""
    R = RF * np.conj(np.fft.rfft(sig, n))
    R /= np.abs(R) + 1e-9
    r = np.fft.irfft(R, n)[:nref - len(sig) + 1]
    k = int(np.argmax(r))
    d = r[k - 1] - 2 * r[k] + r[k + 1] if 0 < k < len(r) - 1 else 0
    frac = 0.5 * (r[k - 1] - r[k + 1]) / d if d else 0.0
    return (k + frac) / SR, float(r[k] / (np.median(np.abs(r)) + 1e-12))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('recording')
    ap.add_argument('--take', action='append', required=True, help='NAME=path (repeatable)')
    ap.add_argument('--outdir', default='work')
    ap.add_argument('--anchors', type=int, default=5)
    ap.add_argument('--win', type=float, default=20)
    a = ap.parse_args()
    ref = pcm(a.recording, SR)
    rec_len = len(ref) / SR
    n = 1 << int(np.ceil(np.log2(len(ref) + a.win * SR + 1)))
    RF = np.fft.rfft(ref, n)
    Path(a.outdir).mkdir(parents=True, exist_ok=True)
    for spec in a.take:
        name, path = spec.split('=', 1)
        info = probe(path)
        dur, off = info['duration'], av_offset(info)
        x = pcm(path, SR)
        win = min(a.win, len(x) / SR)
        pts = list(np.linspace(0, len(x) / SR - win, a.anchors)) if len(x) / SR > win + 1 else [0.0]
        res = []
        for t0 in pts:
            seg = x[int(t0 * SR):int((t0 + win) * SR)]
            if len(seg) < SR or np.sqrt(np.mean(seg ** 2)) < 1e-3:
                continue
            lag, conf = peak(RF, n, len(ref), seg)
            res.append((t0, lag, conf))
        if not res:
            print(f'{name}: no usable camera sound to sync on (silent or no audio track) - skipped')
            continue
        t, L, c = (np.array(v) for v in zip(*res))
        good = c >= max(6.0, 0.4 * c.max())
        s1, a0 = 1.0, None
        if good.sum() >= 3:
            s1, a0 = np.polyfit(t[good], L[good], 1)
            ok = good & (np.abs(L - (a0 + s1 * t)) < 0.03)
            if 3 <= ok.sum() < good.sum():
                s1, a0 = np.polyfit(t[ok], L[ok], 1)
        if a0 is None or abs(s1 - 1) * dur < 0.010:          # drift under 10 ms over the take: ignore it
            s1 = 1.0
            a0 = float(np.median((L - t)[good])) if good.any() else float((L - t)[np.argmax(c)])
        b = float(s1 - 1)
        spread = float(np.std((L - a0 - s1 * t)[good]) * 1000) if good.sum() > 1 else 0.0
        r0 = a0 - s1 * off                                     # recording time at the first video frame
        lead = max(0.0, -r0 / s1)                              # take started before the recording: silence first
        af = (f'atempo={s1:.8f},' if b else '') + (f'adelay={lead * 1000:.0f}:all=1,' if lead else '') + f'apad=whole_dur={dur:.3f}'
        out = Path(a.outdir) / f'{name}.lav.wav'
        part = out.with_name(out.stem + '.part.wav')
        run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-ss', f'{max(r0, 0.0):.4f}', '-t', f'{dur * s1 + 0.3:.3f}',
             '-i', a.recording, '-af', af, '-t', f'{dur:.3f}', '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s24le', part])
        part.replace(out)
        warn = []
        if c.max() < 15:
            warn.append('LOW CONFIDENCE: is this take in this recording? check by ear')
        if spread > 20:
            warn.append(f'anchors disagree by {spread:.0f} ms: check by ear')
        if lead:
            warn.append(f'the take starts {lead:.2f}s before the recording (silence there)')
        if r0 + s1 * dur > rec_len + 0.05:
            warn.append(f'the recording ends {r0 + s1 * dur - rec_len:.2f}s before the take (silence there)')
        print(f'{name}: take starts {r0:.3f}s into the recording | drift {b * 1e6:+.0f} ppm ({b * dur * 1000:+.0f} ms over {dur:.0f}s)'
              f' | anchors {int(good.sum())}/{len(res)} confidence {c.min():.0f}..{c.max():.0f} spread {spread:.1f} ms -> {out}'
              + ''.join(f'\n  WARN {w}' for w in warn))


if __name__ == '__main__':
    main()
