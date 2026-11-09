#!/usr/bin/env python3
"""captions.py - SRT captions for a rendered version (EDIT-WITH-AI.md 4.8). check.py runs this for you.

Usage: captions.py work/edit.json --out output/v1.srt --asr work/check_v1.words.json [--maxchars 32] [--minshow 0.7]
  --asr  words of the RENDERED video (check.py transcribes it): the best source, because they are already on the output
         timeline. Without --asr the captions come from the source words mapped through the edit, which loses words
         right next to cuts (Whisper's word times are too rough for that).
Rules: 1-2 lines, max 32 characters per line (18 for vertical video), break at pauses and sentence ends, at least 0.7 s
on screen. Filler words never appear. Corrections from vocab.json "fix" are applied (Whisper hears "Cloud" for "Claude").
"""
import argparse
import json

from common import fix_text, norm, out_time, size_for, timeline, vocab


def fmt(t):
    ms = int(round(t * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


def two_lines(text, maxc):
    if len(text) <= maxc:
        return text
    best = None
    for i, ch in enumerate(text):
        if ch == ' ':
            l1, l2 = text[:i], text[i + 1:]
            score = abs(len(l1) - len(l2)) + (0 if len(l1) <= maxc and len(l2) <= maxc else 100)
            if best is None or score < best[0]:
                best = (score, l1, l2)
    return f'{best[1]}\n{best[2]}' if best else text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('edit')
    ap.add_argument('--out', required=True)
    ap.add_argument('--asr', help='words.json of the rendered video (from check.py)')
    ap.add_argument('--maxchars', type=int)
    ap.add_argument('--minshow', type=float, default=0.7)
    a = ap.parse_args()
    edit = json.load(open(a.edit, encoding='utf-8'))
    W, H = size_for(edit.get('format', '16:9'))
    maxc = a.maxchars or (32 if W > H else 18)
    v = vocab()
    tl = timeline(edit)
    ws = []
    if a.asr:                                                        # words of the rendered video: already on its timeline
        for w in json.load(open(a.asr, encoding='utf-8')):
            if norm(w['w']) not in v['fillers']:
                ws.append((w['t'] - 0.10, w['t'] + 0.20, w['w']))
    else:
        for src, info in edit['sources'].items():
            for w in json.load(open(info['words'], encoding='utf-8')):
                t = None if norm(w['w']) in v['fillers'] else out_time(tl, src, w['t'])
                if t is not None:
                    ws.append((t - 0.10, t + 0.20, w['w']))
    ws.sort()
    caps, cur = [], []
    for s, e, t in ws:
        if cur:
            text, last = ' '.join(x[2] for x in cur + [(s, e, t)]), cur[-1][2]
            if (s - cur[-1][1] > 0.5 or len(text) > 2 * maxc - 6 or e - cur[0][0] > 6
                    or (last[-1] in '.?!' and len(cur) >= 2)
                    or (last[-1] in ',;:' and len(' '.join(x[2] for x in cur)) > maxc)):
                caps.append(cur)
                cur = []
        cur.append((s, e, t))
    if cur:
        caps.append(cur)
    out = []
    for i, c in enumerate(caps):
        s = max(0.0, c[0][0] - 0.03)
        nxt = caps[i + 1][0][0] - 0.04 if i + 1 < len(caps) else 1e9
        e = max(c[-1][1] + 0.15, min(s + a.minshow, nxt))
        e = min(e, nxt) if nxt > s + 0.2 else e
        text = fix_text(' '.join(x[2] for x in c), edit.get('fix', {}) | v['fix'])
        out.append(f"{i + 1}\n{fmt(s)} --> {fmt(e)}\n{two_lines(text, maxc)}\n")
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out))
    print(f'{len(caps)} captions, {len(ws)} words -> {a.out}')


if __name__ == '__main__':
    main()
