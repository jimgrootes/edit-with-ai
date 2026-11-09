#!/usr/bin/env python3
"""plan.py - from the words you keep to a frame-exact cut list: work/plan.json (you write it) -> work/edit.json.

work/plan.json (see examples/plan.example.json):
{ "format": "16:9", "fps": 30, "loudness": -14, "punch": 1.12,
  "takes": {"main": {"src": "/path/take.MOV", "keep": [[0, 57], [61, 120]]}, "end": {"src": "...", "keep": [[0, 200]]}},
  "order": ["main", "end"],
  "zoom":  [{"take": "main", "from": 51, "to": 70, "zoom": 1.25}],
  "cards": [{"png": "work/cards/prices.png", "at": ["main", 130], "dur": 5}],
  "broll": [{"clip": "/path/clip.MP4", "in": 1.0, "dur": 3.0, "at": ["main", 412], "lut": "assets/luts/x.cube"}],
  "music": {"files": ["assets/music/a.wav", "assets/music/b.wav"], "db": 21} }
  takes  NAME = the --name you gave transcribe.py (and sync.py); keep = [first word #, last word #] ranges, using the
         numbers in work/NAME.transcript.txt (tools/words.py shows exact numbers). Retakes: keep the last good version.
         Optional "lut": "assets/luts/cam.cube" when the take itself was filmed in log.
  order  the takes in the order they play
  punch  zoom of every second talking-head segment, to hide the jump cuts (1.0 = no punch-ins)
  zoom   editor cue "zoom in": segments over words from..to step up to that zoom
  cards  a PNG from card.py shown from the anchor for dur seconds; "at" may also be seconds or "end" (last dur seconds)
  broll  covers the picture from the moment that word is spoken (the voice keeps running); "in" = start inside the clip;
         "lut" = .cube for log footage; "at" may also be seconds on the output timeline
  music  playlist, looped with crossfades; db = how many LU the music sits under the voice (18 louder ... 24 softer)
What it does (EDIT-WITH-AI.md 4.4): pauses over 0.4 s are cut down to 0.15 s of air each side; filler words and stray
noises between words are removed; every cut sits in silence next to the voiced stretches, never inside a word; punch-ins
alternate 1.0 / punch.
Why it cuts on the audio and not on word times: Whisper's word times are only good to a few hundred ms, but the ORDER of
its words is reliable and the audio level is exact. So the words are assigned, in order, to the voiced runs of the
recording (assign()), and the cuts are made on the runs. It errs on the side of keeping: a loud run rarely stays
without a word, and fillers Whisper is unsure of stay in (an extra "uh" is better than a lost word). A filler glued to a
word (no silence between) can't be cut cleanly: those are left in and listed.

Usage: plan.py PROJECT_DIR [--pause 0.4] [--air 0.15]
Reads PROJECT/work/plan.json, NAME.words.json and the take's sound (NAME.lav.wav from sync.py, or the camera audio);
writes PROJECT/work/edit.json; prints a summary.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import ROOT, envelope, mmss, norm, out_time_near, pcm, quiet_point, size_for, take_sound, timeline, vocab

SR, HOP = 16000, 0.010
PMIN = 0.5        # a filler word Whisper is less sure of than this counts as speech: the filler prompt makes it invent
                  # an "uh" now and then where a real word is (seen at p 0.27 and 0.44; real fillers 0.5-1.0)
LOUD_DB = 3.0     # a voiced run peaking this many dB above the median speech level is "loud": in testing those were
LAM_LOUD = 0.4    # nearly always real words with wrong Whisper times, so leaving one without a word costs more;
                  # quieter runs were breaths, noise or "uh"


def voiced_runs(env, close=0.08, minlen=0.05):
    """Runs of speech-level signal [(a, b)] in seconds; quiet holes shorter than `close` are bridged."""
    floor, top = np.percentile(env, 5), np.percentile(env, 95)
    thr = max(floor + 8.0, top - 30.0)
    d = np.diff(np.concatenate([[False], env >= thr, [False]]).astype(np.int8))
    runs = []
    for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
        if runs and a - runs[-1][1] <= close / HOP:
            runs[-1][1] = int(b)
        else:
            runs.append([int(a), int(b)])
    return [(a * HOP, b * HOP + 0.015) for a, b in runs if (b - a) * HOP >= minlen], float(thr)


def assign(W, runs, k0, k1, loud, lam=0.2):
    """Order-preserving assignment of words k0..k1 to voiced runs -> {run index: [word numbers]}.
    Cost = distance (s) between the word's time (either timestamp source) and the run; a run left empty costs lam
    (LAM_LOUD if it is louder than normal speech, 0.05 if it is very short)."""
    ids = [j for j, (a, b) in enumerate(runs) if b > W[k0]['start'] - 1.5 and a < W[k1]['start'] + 1.5]
    if not ids:
        return {}
    R = [runs[j] for j in ids]
    M, N = len(R), k1 - k0 + 1
    dist = lambda t, r: 0.0 if r[0] <= t <= r[1] else min(abs(t - r[0]), abs(t - r[1]))
    cost = np.array([[min(dist(W[k]['start'], r), dist(W[k]['hs'], r)) for r in R] for k in range(k0, k1 + 1)])
    pen = np.array([LAM_LOUD if loud[j] else (lam if b - a >= 0.12 else 0.05) for j, (a, b) in zip(ids, R)])
    dp, bp = cost.copy(), np.zeros((N, M), int)
    for k in range(1, N):
        best, arg = 1e9, -1
        for j in range(M):
            if j > 0:
                nb = best + pen[j - 1] if arg >= 0 else 1e9
                if dp[k - 1][j - 1] <= nb:
                    best, arg = dp[k - 1][j - 1], j - 1
                else:
                    best = nb
            if dp[k - 1][j] <= best:
                dp[k][j], bp[k][j] = dp[k - 1][j] + cost[k][j], j
            else:
                dp[k][j], bp[k][j] = best + cost[k][j], arg
    j, held = int(np.argmin(dp[N - 1])), {}
    for k in range(N - 1, -1, -1):
        held.setdefault(ids[j], []).insert(0, k0 + k)
        j = bp[k][j]
    return held


def cut_range(W, env, runs, loud, i0, i1, air, pause, lvl, fillers):
    """Kept [in, out] pieces (take time) for words i0..i1.
    Returns pieces, number of cuts, filler runs removed, glued fillers left in, and the word numbers that stay in."""
    held = assign(W, runs, max(0, i0 - 8), min(len(W) - 1, i1 + 8), loud)
    isf = lambda k: norm(W[k]['w']) in fillers and W[k].get('p', 1.0) >= PMIN
    of = {k: ri for ri, ks in held.items() for k in ks}
    ri0, ri1 = of.get(i0), of.get(i1)
    if ri0 is not None and min(held[ri0]) >= i0:            # first word opens its run: cut in the silence before it
        a = runs[ri0][0]
        t_in = max(a - air, ((runs[ri0 - 1][1] if ri0 else 0.0) + a) / 2, 0.0)
    else:                                                   # glued to the previous word (a retake splice): quietest spot
        s0 = W[i0]['hs']
        t_in = quiet_point(env, s0, s0 - 0.12, s0 + 0.03)
    if ri1 is not None and max(held[ri1]) <= i1:            # last word closes its run: cut in the silence after it
        b = runs[ri1][1]
        t_out = min(b + air, (b + (runs[ri1 + 1][0] if ri1 + 1 < len(runs) else b + 2 * air)) / 2)
    else:
        e1 = W[i1]['he']
        t_out = quiet_point(env, e1, e1 - 0.10, e1 + 0.10)
    t_in, t_out = max(t_in, 0.0), min(t_out, len(env) * HOP)
    typed, cuts, left = [], [], []
    for ri, (a, b) in enumerate(runs):
        if b <= t_in or a >= t_out:
            continue
        ws = [k for k in held.get(ri, []) if i0 <= k <= i1]
        if ws:
            kind = 'speech' if any(not isf(k) for k in ws) else 'filler'
        else:                                               # a sound Whisper gave no word to: breath, click, dropped "uh"
            kind = 'speech' if (b - a) >= 0.8 else 'filler'
        typed.append((a, b, kind, ws))
    kept = [r for r in typed if r[2] == 'speech']
    for (a1, b1, _, _), (a2, b2, _, _) in zip(kept, kept[1:]):
        fl = [r for r in typed if r[2] == 'filler' and r[0] >= b1 - 1e-6 and r[1] <= a2 + 1e-6]
        between = bool(fl)
        if a2 - b1 > pause or between:
            c0, c1 = b1 + air, a2 - air
            if fl:                               # take a filler/noise out whole, also when it sits close to the speech
                c0 = max(b1 + 0.02, min(c0, fl[0][0] - 0.01))
                c1 = min(a2 - 0.02, max(c1, fl[-1][1] + 0.01))
            if c1 - c0 < 0.04:
                c0, c1 = b1 + 0.02, a2 - 0.02
                if not between or c1 - c0 < 0.04:
                    continue
            cuts.append((c0, c1))
    n_fill = sum(1 for r in typed if r[2] == 'filler')
    dip = lambda t: float(np.mean(env[int((t - 0.025) / HOP):int((t + 0.025) / HOP) + 1]))
    for a, b, kind, ws in kept:                              # fillers glued to the start or end of a speech run
        if len(ws) < 2:
            continue
        if isf(ws[0]):
            g = quiet_point(env, a + 0.3, a + 0.15, a + 0.6)
            if dip(g) < lvl - 10 and g - a < b - a - 0.2:
                cuts.append((a, g))
                n_fill += 1
        if isf(ws[-1]):
            g = quiet_point(env, b - 0.3, b - 0.6, b - 0.15)
            if dip(g) < lvl - 10 and b - g < b - a - 0.2:
                cuts.append((g, b))
                n_fill += 1
        left += [k for k in ws[1:-1] if isf(k)]
    pieces, cur = [], t_in
    for c0, c1 in sorted(cuts):
        if c0 > cur:
            pieces.append((cur, c0))
        cur = max(cur, c1)
    pieces.append((cur, t_out))
    pieces = [(x, y) for x, y in pieces if y - x >= 0.25]
    said = [k for k in range(i0, i1 + 1) if k in of and
            any(min(y, runs[of[k]][1]) - max(x, runs[of[k]][0]) > 0.02 for x, y in pieces)]
    return pieces, len(cuts), n_fill, left, said


def anchor(at, plan, words, tl, what, dur=0.0):
    """[take, word #] | seconds on the output timeline | "end" -> seconds on the output timeline."""
    total = tl['total'] / tl['fps']
    if at == 'end':
        return round(total - dur, 3)
    if isinstance(at, (int, float)):
        return float(at)
    take, idx = at
    if take not in words or not 0 <= idx < len(words[take]):
        raise SystemExit(f'{what}: anchor {at} is not a word of a take in "order"')
    t = out_time_near(tl, plan['takes'][take]['src'], words[take][idx]['t'])
    if t is None:
        raise SystemExit(f"{what}: word {idx} of '{take}' ({words[take][idx]['w']!r}) is not part of the edit")
    return round(t, 3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project')
    ap.add_argument('--pause', type=float, default=0.4)
    ap.add_argument('--air', type=float, default=0.15)
    a = ap.parse_args()
    proj = Path(a.project) if Path(a.project).is_absolute() else ROOT / a.project
    work = proj / 'work'
    plan = json.load(open(work / 'plan.json', encoding='utf-8'))
    fps, fmt, punch = plan.get('fps', 30), plan.get('format', '16:9'), plan.get('punch', 1.12)
    size_for(fmt)
    fillers = vocab()['fillers']
    segs, sources, words, spoken = [], {}, {}, []
    for name in plan['order']:
        t = plan['takes'][name]
        wp = work / f'{name}.words.json'
        if not wp.exists():
            raise SystemExit(f'{wp} is missing: transcribe.py ... --name {name}')
        W = words[name] = json.load(open(wp, encoding='utf-8'))
        snd = take_sound(work, name, t['src'])
        env = envelope(pcm(snd, SR), SR, HOP)
        runs, thr = voiced_runs(env)
        sources[t['src']] = {'audio': str(snd), 'words': str(wp)}
        n_seg = n_cut = n_fill = 0
        span = kept = 0.0
        lvl = float(np.median(env[env >= thr]))
        loud = [float(env[int(a / HOP):max(int(a / HOP) + 1, int(b / HOP))].max()) >= lvl + LOUD_DB for a, b in runs]
        left = []
        for i0, i1 in t['keep']:
            if not 0 <= i0 <= i1 < len(W):
                raise SystemExit(f'{name}: keep range [{i0}, {i1}] is outside words 0..{len(W) - 1}')
            pcs, nc, nf, sk, said = cut_range(W, env, runs, loud, i0, i1, a.air, a.pause, lvl, fillers)
            spoken.append({'src': t['src'], 'idx': said})
            n_cut, n_fill = n_cut + nc, n_fill + nf
            left += sk
            span += W[i1]['end'] - W[i0]['start']
            for k, (x, y) in enumerate(pcs):
                segs.append({'src': t['src'], 'take': name, 'in': round(x, 3), 'out': round(y, 3),
                             'note': ' '.join(w['w'] for w in W[i0:i0 + 6]) if k == 0 else ''})
                if t.get('lut'):
                    segs[-1]['lut'] = t['lut']
                kept += y - x
                n_seg += 1
        print(f"{name}: {len(t['keep'])} ranges -> {n_seg} segments | {n_cut} cuts, {n_fill} filler/noise runs removed | "
              f"{span:.0f}s of chosen speech -> {kept:.0f}s kept ({rel_snd(snd)}, threshold {thr:.0f} dB)"
              + (f"\n  {len(left)} filler(s) glued to a word, left in: words {left[:12]}" if left else ''))
    zoomed = set()                                           # editor cue "zoom in": steps up to the full zoom over that stretch
    for z in plan.get('zoom', []):
        t0, t1 = words[z['take']][z['from']]['t'] - 0.3, words[z['take']][z['to']]['t'] + 0.3
        hit = [k for k, s in enumerate(segs) if s['take'] == z['take'] and s['out'] > t0 and s['in'] < t1]
        for n, k in enumerate(hit):
            segs[k]['punch'] = round(1.0 + (z['zoom'] - 1.0) * (n + 1) / len(hit), 3)
            zoomed.add(k)
    n = 0
    for k, s in enumerate(segs):
        if k not in zoomed:
            s['punch'] = 1.0 if n % 2 == 0 else punch
            n += 1
    edit = {'format': fmt, 'fps': fps, 'loudness': plan.get('loudness', -14), 'segments': segs,
            'captions': plan.get('captions', True), 'sources': sources, 'spoken': spoken}
    if plan.get('music'):
        edit['music'] = plan['music']
    tl = timeline(edit)
    placed = []
    for b in plan.get('broll', []):
        t = anchor(b['at'], plan, words, tl, f"b-roll {Path(b['clip']).name}")
        seg = {'src': b['clip'], 'in': b.get('in', 0.0), 'dur': b['dur'], 'over': True, 'at': t}
        if b.get('lut'):
            seg['lut'] = b['lut']
        edit['segments'].append(seg)
        placed.append(f"{mmss(t)}+{b['dur']}s")
    cards = []
    for c in plan.get('cards', []):
        png = Path(c['png']) if Path(c['png']).is_absolute() else ROOT / c['png']
        if not png.exists():
            png = proj / c['png'] if (proj / c['png']).exists() else png
        if not png.exists():
            raise SystemExit(f"card {c['png']} does not exist yet: make it with card.py first")
        t = anchor(c['at'], plan, words, tl, f"card {png.name}", c['dur'])
        edit.setdefault('overlays', []).append({'png': str(png), 'at': t, 'dur': c['dur'], 'fade': c.get('fade', 0.25)})
        cards.append(f"{mmss(t)}+{c['dur']}s")
    tl = timeline(edit)                                              # validates b-roll and card placement
    json.dump(edit, open(work / 'edit.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f"edit.json: {len(segs)} segments, {tl['total'] / fps:.1f}s ({mmss(tl['total'] / fps)}), {fmt} {fps} fps, "
          f"{len(tl['pieces'])} picture pieces, b-roll at {', '.join(placed) or 'none'}, cards at {', '.join(cards) or 'none'}")


def rel_snd(p):
    return 'lav' if str(p).endswith('.lav.wav') else 'camera audio'


if __name__ == '__main__':
    main()
