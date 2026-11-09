#!/usr/bin/env python3
"""check.py - quality control of a rendered version, and its captions (EDIT-WITH-AI.md 4.10).

Usage: check.py output/vN.mp4 --project projects/NAME [--every 20] [--no-asr]
PASS/WARN per check (thresholds below):
  length      within 0.1 s of what edit.json says
  picture     the output size and fps of edit.json, colour tags bt709
  loudness    integrated within +-1 LU of the target, true peak at most -1.0 dBTP
  black       no black stretch of 0.1 s or longer
  faces       a face is found on every sampled talking-head frame, not cut off by the frame edge, no card over it
  words       the render is transcribed again and compared with the words the edit should contain:
              93% or more = PASS. Below that, listen at the listed times. Under 85% something is structurally wrong
              (wrong take, bad sync). ASR can't PROVE a word is clipped: a quiet short word is often "missed" while it
              is there. The listed times are places to LISTEN, not errors. Fillers it still hears are listed too.
Writes output/vN.srt (captions from this transcription, see captions.py) and output/vN_sheet.jpg (contact sheet: look
at it once). Prints only short lines.
"""
import argparse
import difflib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from common import MODELS, PY, ROOT, TOOLS, fix_text, mmss, norm, out_time, rel, run, size_for, timeline, vocab
from probe import probe
from sheet import grid, frame

WORDS_PASS, WORDS_BAD = 0.93, 0.85
LU_TOL, TP_MAX, BLACK_MIN = 1.0, -1.0, 0.1


def loudness(path, target):
    r = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-af',
                        f'loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True)
    j = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S).group(0))
    return float(j['input_i']), float(j['input_tp']), float(j['input_lra'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--project', required=True)
    ap.add_argument('--every', type=float, help='seconds between contact-sheet frames (default: about 36 frames)')
    ap.add_argument('--no-asr', action='store_true', help='skip the transcription (no word check, captions from the edit)')
    a = ap.parse_args()
    v = Path(a.video)
    proj = Path(a.project) if Path(a.project).is_absolute() else ROOT / a.project
    work = proj / 'work'
    edit = json.load(open(work / 'edit.json', encoding='utf-8'))
    tl = timeline(edit)
    W, H = size_for(edit.get('format', '16:9'))
    voc = vocab()
    fix = edit.get('fix', {}) | voc['fix']
    o = probe(v)
    vi, au = o['video'], o['audio']
    bad = [0]

    def flag(ok, msg):
        print(('PASS ' if ok else 'WARN ') + msg)
        bad[0] += not ok
    exp = tl['total'] / tl['fps']
    flag(abs(o['duration'] - exp) < 0.1, f"length {o['duration']:.2f}s (edit says {exp:.2f}s), {o['mb']:.0f} MB")
    flag(vi['display'] == [W, H] and abs(vi['fps_float'] - tl['fps']) < 0.01,
         f"picture {vi['display'][0]}x{vi['display'][1]} {vi['fps']} {vi['codec']} {vi['pix_fmt']}; audio {au['codec']} {au['ch']}ch {au['rate']} Hz")
    flag(vi['color'][:3] == ['bt709'] * 3, f"colour tags {'/'.join(map(str, vi['color']))}")
    I, TP, LRA = loudness(v, edit['loudness'])
    flag(abs(I - edit['loudness']) <= LU_TOL and TP <= TP_MAX,
         f"loudness {I:.1f} LUFS (target {edit['loudness']}), true peak {TP:.1f} dBTP, LRA {LRA:.1f}")
    r = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(v), '-vf', f'blackdetect=d={BLACK_MIN}:pix_th=0.04', '-an',
                        '-f', 'null', '-'], capture_output=True, text=True)
    black = re.findall(r'black_start:([\d.]+)', r.stderr)
    flag(not black, 'no black frames' if not black else f'black frames at {", ".join(mmss(float(b)) for b in black[:6])}')

    every = a.every or min(20.0, max(1.0, exp / 36))
    ts = np.arange(min(0.5, exp / 2), exp - 0.1, every)
    tiles = [(frame(v, t, 320), mmss(t)) for t in ts]
    sheet = v.with_name(v.stem + '_sheet.jpg')
    grid(tiles, 6).save(sheet, quality=82)
    yunet = MODELS / 'face_detection_yunet_2023mar.onnx'
    if yunet.exists():
        import cv2
        from faces import detect
        th = [(t, im) for t, (im, _) in zip(ts, tiles)
              if any(p['kind'] == 'th' and p['start'] <= t * tl['fps'] < p['start'] + p['frames'] for p in tl['pieces'])]
        from PIL import Image
        boxes = {}                                                   # opaque part of each card, in output pixels
        for c in tl['overlays']:
            if c['png'] not in boxes and Path(c['png']).exists():
                boxes[c['png']] = Image.open(c['png']).getchannel('A').point(lambda x: 255 if x > 128 else 0).getbbox()
        miss, edge, under = [], [], []
        for t, im in th:
            arr = cv2.cvtColor(np.asarray(im.resize((im.width * 2, im.height * 2))), cv2.COLOR_RGB2BGR)
            f = detect(arr, 0.6)
            if f is None:
                miss.append(mmss(t))
                continue
            if min(f[0], f[1], arr.shape[1] - f[0] - f[2], arr.shape[0] - f[1] - f[3]) < -0.12 * f[3]:   # sticks out
                edge.append(mmss(t))
            k = W / arr.shape[1]
            fx0, fy0, fx1, fy1 = f[0] * k, f[1] * k, (f[0] + f[2]) * k, (f[1] + f[3]) * k
            for c in tl['overlays']:
                b = boxes.get(c['png'])
                if b and c['a'] <= t * tl['fps'] < c['a'] + c['n'] and b[0] < fx1 and fx0 < b[2] and b[1] < fy1 and fy0 < b[3]:
                    under.append(mmss(t))
        flag(not miss and not edge and not under, f'faces: found on {len(th) - len(miss)}/{len(th)} talking-head frames'
             + (f'; NO face at {", ".join(miss[:8])}' if miss else '') + (f'; cut off by the edge at {", ".join(edge[:8])}' if edge else '')
             + (f'; a card covers the face at {", ".join(sorted(set(under))[:8])}' if under else ''))

    asr = None
    if not a.no_asr:
        run([PY, TOOLS / 'transcribe.py', v, '--name', f'check_{v.stem}', '--outdir', work])
        asr = work / f'check_{v.stem}.words.json'
        heard = json.load(open(asr, encoding='utf-8'))
        expw, cache = [], {}
        for part in edit.get('spoken', []):                         # the words plan.py kept, in playing order
            if part['src'] not in cache:
                cache[part['src']] = json.load(open(edit['sources'][part['src']]['words'], encoding='utf-8'))
            expw += [(0, cache[part['src']][k]['w']) for k in part['idx']
                     if norm(cache[part['src']][k]['w']) not in voc['fillers']]
        if not expw:                                                # edit.json from an older plan.py
            for src, info in edit['sources'].items():
                for w in json.load(open(info['words'], encoding='utf-8')):
                    t = out_time(tl, src, w['t'])
                    if t is not None and norm(w['w']) not in voc['fillers']:
                        expw.append((t, w['w']))
            expw.sort()
        clean = lambda ws: [norm(x) for t, w in ws for x in fix_text(w, fix).split() if norm(x)]
        ew = clean(expw)
        hw_t = [(w['t'], x) for w in heard for x in fix_text(w['w'], fix).split() if norm(x)]
        fills = [mmss(t) for t, x in hw_t if norm(x) in voc['fillers']]
        hw_t = [(t, x) for t, x in hw_t if norm(x) not in voc['fillers']]
        hw = [norm(x) for _, x in hw_t]
        sm = difflib.SequenceMatcher(None, ew, hw, autojunk=False)
        diffs = [(tag, ' '.join(ew[i1:i2]), ' '.join(hw[j1:j2]), hw_t[min(j1, len(hw_t) - 1)][0])
                 for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal']
        ratio = sm.ratio()
        verdict = '' if ratio >= WORDS_PASS else (' - listen at these times' if ratio >= WORDS_BAD else
                                                  ' - STRUCTURAL problem? (wrong take, bad sync, missing piece)')
        flag(ratio >= WORDS_PASS, f"words: {ratio * 100:.1f}% match with the intended text ({len(ew)} expected, {len(hw)} heard){verdict}")
        for tag, e, h, t in diffs[:14]:
            print(f"     {mmss(t)}  expected '{e[:50]}'  heard '{h[:50]}'")
        if len(diffs) > 14:
            print(f'     ... and {len(diffs) - 14} more differences')
        print(f"INFO fillers still heard: {len(fills)}" + (f" at {', '.join(fills[:12])}" if fills else ''))
    srt = v.with_suffix('.srt')
    cmd = [PY, TOOLS / 'captions.py', work / 'edit.json', '--out', srt] + (['--asr', asr] if asr else [])
    print(run(cmd).stdout.strip())
    print(f'sheet: {len(tiles)} frames every {every:g}s -> {rel(sheet)}')
    print('RESULT:', 'all checks passed' if not bad[0] else f'{bad[0]} warning(s)')


if __name__ == '__main__':
    main()
