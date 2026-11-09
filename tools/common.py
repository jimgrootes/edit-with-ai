"""common.py - helpers shared by the tools (imported, not run).

Workspace = the folder that holds EDIT-WITH-AI.md and tools/. Optional vocab.json in that folder (see vocab()) holds the
spoken language, the filler prompt and extra filler words for it, and corrections for words Whisper mishears (names).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault('OPENCV_LOG_LEVEL', 'ERROR')     # OpenCV 5 prints a harmless backend warning per face detector
ROOT = Path(__file__).resolve().parent.parent          # the workspace folder
TOOLS = ROOT / 'tools'
MODELS = TOOLS / 'models'
PY = sys.executable                                    # the Python running this tool (the venv), used to call other tools
FILLERS = {'uh', 'um', 'uhm', 'umm', 'uhh', 'er', 'erm', 'ah', 'eh', 'ehm', 'hmm', 'mm', 'mhm'}
FORMATS = {'16:9': (1920, 1080), '9:16': (1080, 1920), '1:1': (1080, 1080), '4:5': (1080, 1350)}


def run(cmd, check=True, cwd=None):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(str(c) for c in cmd)[:200]}\n{r.stderr[-600:]}")
    return r


def norm(word):
    """Lowercase, letters/digits/apostrophes only (any alphabet), for comparing words."""
    return re.sub(r"[^\w']|_", '', word.lower())


def key(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def mmss(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def rel(p):
    """Path relative to the workspace when it is inside it (shorter output), else as given."""
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def size_for(fmt):
    if fmt not in FORMATS:
        raise SystemExit(f'unknown format {fmt!r}: use one of {", ".join(FORMATS)}')
    return FORMATS[fmt]


def vocab():
    """vocab.json in the workspace: language and vocabulary (all keys optional):
      "lang":    "en"                         the language you speak in your videos (Whisper language code)
      "prompt":  "Umm, uh, so, like, okay."   a sentence with fillers IN THAT LANGUAGE: makes Whisper keep "uh/um"
      "fillers": ["ehm", "nou"]              extra filler words to cut, on top of the English ones
      "fix":     {"cloud": "Claude", "Entropic's": "Anthropic's"}   corrections for captions and checks
    A "fix" key with a capital letter only matches that exact spelling; an all-lowercase key matches any case ("cloud"
    also fixes "Cloud"; leave it out if you also say the real word). Keys may be several words ("jim grooves").
    Don't put names in the prompt: in testing that made Whisper drop every filler and the first seconds of speech.
    Names Whisper gets wrong go in "fix"."""
    p = ROOT / 'vocab.json'
    v = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    v.setdefault('lang', 'en')
    v.setdefault('prompt', 'Umm, uh, so, like, okay.')
    v['fillers'] = FILLERS | {norm(w) for w in v.get('fillers', [])}
    v.setdefault('fix', {})
    return v


def fix_text(text, fix):
    """Apply vocabulary corrections to a piece of text (whole words only, longest keys first)."""
    for k in sorted(fix, key=len, reverse=True):
        text = re.sub(rf'(?<!\w){re.escape(k)}(?!\w)', lambda m, v=fix[k]: v, text, flags=re.I if k == k.lower() else 0)
    return text


def pcm(path, sr=16000, start=None, dur=None):
    """Any audio/video file -> mono float32 numpy array at `sr` Hz."""
    cmd = ['ffmpeg', '-v', 'error', '-nostdin']
    if start:
        cmd += ['-ss', f'{start:.3f}']
    if dur:
        cmd += ['-t', f'{dur:.3f}']
    cmd += ['-i', str(path), '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-400:])
    return np.frombuffer(r.stdout, dtype=np.float32)


def av_offset(info):
    """Seconds from the start of a camera file (its earliest stream, = time 0 for the tools) to its first audio sample.
    Usually 0. From probe()."""
    try:
        a = float(info['audio']['start'] or 0)
        v = float(info['video']['start'] or 0) if info.get('video') else a
        return max(0.0, a - min(a, v))
    except (KeyError, TypeError, ValueError):
        return 0.0


def take_sound(work, name, src):
    """The sound of a take on the take's own clock: work/NAME.lav.wav from sync.py if it exists, otherwise the camera's
    audio, extracted once to work/NAME.cam.wav (48 kHz mono)."""
    from probe import probe
    lav = Path(work) / f'{name}.lav.wav'
    if lav.exists():
        return lav
    cam = Path(work) / f'{name}.cam.wav'
    if not cam.exists():
        info = probe(src)
        if not info.get('audio'):
            raise SystemExit(f'{name}: {Path(src).name} has no audio. Sync a separate recording first (sync.py).')
        off = av_offset(info)
        af = f'adelay={off * 1000:.0f}:all=1' if off > 0.001 else 'anull'
        run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-i', src, '-vn', '-af', af, '-ac', '1', '-ar', '48000',
             '-c:a', 'pcm_s24le', str(cam) + '.part.wav'])
        os.replace(str(cam) + '.part.wav', cam)
    return cam


def envelope(x, sr, hop=0.010, win=0.025):
    """Short-time RMS in dB, one value per `hop` s (value i covers i*hop .. i*hop+win)."""
    h, w = int(round(sr * hop)), int(round(sr * win))
    n = max(0, (len(x) - w) // h + 1)
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    i = np.arange(n) * h
    return 10 * np.log10((c[i + w] - c[i]) / w + 1e-10)


def quiet_point(env, t, lo, hi, hop=0.010, win=0.050, bias=10.0):
    """Centre (s) of the quietest `win`-long window inside [lo, hi]; `bias` dB per second pulls it towards t."""
    k = max(1, int(round(win / hop)))
    i0 = max(0, int(round(lo / hop)))
    i1 = min(len(env) - k, int(round((hi - win) / hop)))
    if i1 <= i0:
        return float(min(max(t, lo), hi))
    c = np.concatenate([[0.0], np.cumsum(env[i0:i1 + k])])
    m = (c[k:] - c[:-k]) / k
    cen = np.arange(i0, i1 + 1) * hop + win / 2 + 0.0075
    return float(cen[int(np.argmin(m + bias * np.abs(cen - t)))])


def timeline(edit):
    """edit.json -> frame-exact pieces. Segments with "over": true (b-roll) replace the picture only, from "at" seconds
    on the output timeline; "overlays" (cards) are PNGs shown over the picture from "at" for "dur" seconds."""
    fps = edit.get('fps', 30)
    th, ov, total = [], [], 0
    for s in edit['segments']:
        if s.get('over'):
            ov.append(dict(s, a=round(s['at'] * fps), n=round(s['dur'] * fps)))
            continue
        t = dict(s)
        t['in'] = round(s['in'] * fps) / fps                       # snap to the frame grid
        t['start'], t['frames'] = total, round((s['out'] - s['in']) * fps)
        th.append(t)
        total += t['frames']
    ov.sort(key=lambda o: o['a'])
    for o in ov:
        if o['a'] < 0 or o['a'] + o['n'] > total:
            raise SystemExit(f"b-roll at {o['at']}s runs outside the video ({total / fps:.1f}s)")
    for p, q in zip(ov, ov[1:]):
        if p['a'] + p['n'] > q['a']:
            raise SystemExit(f"b-roll inserts overlap at {q['at']}s")
    inside = lambda c: any(o['a'] < c < o['a'] + o['n'] for o in ov)
    cuts = {0, total} | {o['a'] for o in ov} | {o['a'] + o['n'] for o in ov}
    cuts |= {c for t in th for c in (t['start'], t['start'] + t['frames']) if not inside(c)}
    pieces = []
    cuts = sorted(cuts)
    for a, b in zip(cuts, cuts[1:]):
        o = next((o for o in ov if o['a'] <= a < o['a'] + o['n']), None)
        if o:
            pieces.append({'kind': 'broll', 'src': o['src'], 'start': a, 'frames': b - a,
                           'in': o['in'] + (a - o['a']) / fps, 'lut': o.get('lut')})
        else:
            t = next(t for t in th if t['start'] <= a < t['start'] + t['frames'])
            pieces.append({'kind': 'th', 'src': t['src'], 'start': a, 'frames': b - a,
                           'in': t['in'] + (a - t['start']) / fps, 'punch': t.get('punch', 1.0), 'lut': t.get('lut')})
    cards = []
    for c in edit.get('overlays', []):
        a, n = round(c['at'] * fps), round(c['dur'] * fps)
        if a < 0 or n < 1 or a + n > total:
            raise SystemExit(f"card {Path(c['png']).name} at {c['at']}s for {c['dur']}s runs outside the video ({total / fps:.1f}s)")
        cards.append(dict(c, a=a, n=n))
    return {'fps': fps, 'total': total, 'th': th, 'pieces': pieces, 'overlays': cards}


def out_time(tl, src, t):
    """Time t (s) in take `src` -> seconds on the output timeline, or None if that moment is cut."""
    for s in tl['th']:
        if s['src'] == src and s['in'] <= t < s['in'] + s['frames'] / tl['fps']:
            return (s['start'] + (t - s['in']) * tl['fps']) / tl['fps']
    return None


def out_time_near(tl, src, t, reach=1.0):
    """Like out_time, but a moment that was cut (a removed pause next to the word) snaps to the nearest kept moment
    within `reach` seconds. Word times from Whisper can be off by a few hundred ms."""
    o = out_time(tl, src, t)
    if o is not None:
        return o
    best = None
    for s in tl['th']:
        if s['src'] != src:
            continue
        a, b = s['in'], s['in'] + (s['frames'] - 1) / tl['fps']
        x = min(max(t, a), b)
        if abs(x - t) <= reach and (best is None or abs(x - t) < abs(best - t)):
            best = x
    return None if best is None else out_time(tl, src, best)
