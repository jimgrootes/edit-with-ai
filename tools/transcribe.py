#!/usr/bin/env python3
"""transcribe.py - speech to numbered words with times (whisper.cpp), plus a readable transcript.

Usage: transcribe.py AUDIO_OR_VIDEO --name NAME [--outdir work] [--lang xx] [--model tools/models/ggml-medium.bin]
                     [--prompt "..."]
NAME = the short take name you use everywhere (sync.py --take NAME=..., plan.json "takes").
Writes OUTDIR/NAME.words.json  [{"w": word, "start": s, "end": s, "hs": s, "he": s, "t": s, "p": 0-1}]  and
OUTDIR/NAME.transcript.txt with one line per sentence: `[mm:ss.s #n] text` (start time and number of the first word on
the line). The word numbers are what you put in plan.json. Prints one summary line.

Transcribe the take's sound: work/NAME.lav.wav after sync.py, otherwise the video file itself.
The filler prompt (vocab.json "prompt", default "Umm, uh, so, like, okay.") makes Whisper keep "uh/um". It is passed with
--carry-initial-prompt: without that flag whisper.cpp only uses the prompt for the first 30 s and drops every filler
after that. Keep the prompt to fillers: adding names to it made Whisper drop all fillers and the first seconds of
speech in testing. Names it mishears are fixed afterwards with vocab.json "fix".
Word times: "start" = DTW time, "hs"/"he" = Whisper's own token times, "t" = the average. All of them can be off by a few
hundred ms (sometimes more than 1 s), so never cut on them directly: plan.py cuts on the audio level instead.
"p" = Whisper's confidence in the word. The filler prompt sometimes makes Whisper invent an "uh" where a real word
is (seen at p 0.44, real fillers 0.78-0.99): plan.py only cuts fillers it is confident about.
whisper.cpp: set WHISPER_CLI if whisper-cli is not on your PATH. Needs a recent build (-dtw, --carry-initial-prompt).
"""
import argparse
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np

from common import MODELS, norm, run, vocab

DTW = {'tiny', 'tiny.en', 'base', 'base.en', 'small', 'small.en', 'medium', 'medium.en',
       'large.v1', 'large.v2', 'large.v3', 'large.v3.turbo'}


def dtw_name(model):                       # ggml-large-v3-turbo.bin -> large.v3.turbo, ggml-medium-q5_0.bin -> medium
    n = re.sub(r'^ggml-|\.bin$', '', Path(model).name)
    n = re.sub(r'-q\d+(_\d+|_k)?$', '', n).replace('-', '.')
    return n if n in DTW else None


def default_model():
    if os.environ.get('WHISPER_MODEL'):
        return os.environ['WHISPER_MODEL']
    m = MODELS / 'ggml-medium.bin'
    found = sorted(MODELS.glob('ggml-*.bin')) if MODELS.exists() else []
    return str(m if m.exists() or not found else found[0])


def whisper_bin():
    w = os.environ.get('WHISPER_CLI') or shutil.which('whisper-cli') or shutil.which('whisper-cli.exe')
    if not w:
        raise SystemExit('whisper-cli not found. macOS: brew install whisper-cpp. Windows: whisper-bin-x64.zip from '
                         'github.com/ggml-org/whisper.cpp/releases. Linux: build whisper.cpp. Or set WHISPER_CLI=/path/to/whisper-cli')
    return w


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('--name', required=True)
    ap.add_argument('--outdir', default='work')
    ap.add_argument('--lang', help='language code (default: vocab.json "lang", else en)')
    ap.add_argument('--model', default=default_model(), help='default: tools/models/ggml-medium.bin (or WHISPER_MODEL)')
    ap.add_argument('--prompt', help='filler prompt (default: vocab.json "prompt")')
    a = ap.parse_args()
    if not Path(a.model).exists():
        raise SystemExit(f'no Whisper model at {a.model}: run tools/fetch_models.py first')
    v = vocab()
    prompt, lang = a.prompt or v['prompt'], a.lang or v['lang']
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    wav, base = out / f'{a.name}.16k.wav', out / a.name
    run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-i', a.src, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', wav])
    Path(f'{base}.json').unlink(missing_ok=True)            # whisper-cli exits 0 on an unknown flag and writes nothing:
    cmd = [whisper_bin(), '-m', a.model, '-f', wav, '-l', lang, '-ojf', '-of', base,     # an old JSON must not survive
           '-t', str(min(8, os.cpu_count() or 4)), '--prompt', prompt, '--carry-initial-prompt']
    if dtw_name(a.model):
        cmd += ['-dtw', dtw_name(a.model), '-nfa']           # DTW token times need flash attention off
    r = run(cmd)
    if not Path(f'{base}.json').exists():
        raise SystemExit('whisper-cli wrote no JSON (old build? it needs -dtw and --carry-initial-prompt). Output: '
                         + (r.stdout + r.stderr)[-300:])
    j = json.load(open(f'{base}.json', encoding='utf-8'))
    toks = [tk for seg in j['transcription'] for tk in seg.get('tokens', []) if not re.fullmatch(r'\[_.*\]', tk['text'].strip())]
    pairs = [(tk['t_dtw'], tk['offsets']['from']) for tk in toks if tk.get('t_dtw', -1) >= 0]
    cs = np.median([abs(d * 10 - f) for d, f in pairs]) if pairs else 1e9      # t_dtw in 10 ms units or in ms?
    ms = np.median([abs(d - f) for d, f in pairs]) if pairs else 1e9
    unit = 0.01 if cs <= ms else 0.001
    words = []
    for tk in toks:
        t, o = tk['text'], tk['offsets']
        s = tk['t_dtw'] * unit if tk.get('t_dtw', -1) >= 0 else o['from'] / 1000
        p = round(float(tk.get('p', 1.0)), 3) if re.search(r'\w', t) else 1.0      # punctuation doesn't count
        if t.startswith(' ') or not words:
            words.append({'w': t.strip(), 'start': s, 'hs': o['from'] / 1000, 'end': o['to'] / 1000, 'p': p})
        else:
            words[-1]['w'] += t
            words[-1]['end'] = o['to'] / 1000
            words[-1]['p'] = min(words[-1]['p'], p)
    words = [w for w in words if re.search(r'\w', w['w']) and not re.fullmatch(r'[\[(].*[\])]', w['w'])]
    prev = 0.0
    for i, w in enumerate(words):
        w['start'] = max(w['start'], prev)       # start = DTW time, hs/he = Whisper's own token times, t = best guess
        prev = w['start']
        w['he'] = round(max(w['end'], w['hs'] + 0.03), 3)
        nxt = words[i + 1]['start'] if i + 1 < len(words) else w['end']
        w['end'] = round(max(w['start'] + 0.03, min(w['end'], max(nxt, w['start'] + 0.03))), 3)
        w['start'], w['hs'] = round(w['start'], 3), round(w['hs'], 3)
        w['t'] = round((w['start'] + w['hs']) / 2, 3)
    json.dump(words, open(out / f'{a.name}.words.json', 'w', encoding='utf-8'), ensure_ascii=False)
    lines, cur, texts = [], [], []
    for i, w in enumerate(words):
        cur.append(i)
        gap = words[i + 1]['start'] - w['end'] if i + 1 < len(words) else 9
        if w['w'][-1] in '.?!' or len(cur) >= 28 or gap >= 1.5 or i + 1 == len(words):
            s = words[cur[0]]['start']
            texts.append(' '.join(norm(words[k]['w']) for k in cur))
            lines.append(f"[{int(s // 60):02d}:{s % 60:04.1f} #{cur[0]}] " + ' '.join(words[k]['w'] for k in cur))
            cur = []
    (out / f'{a.name}.transcript.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    fill = sum(norm(w['w']) in v['fillers'] for w in words)
    span = words[-1]['end'] if words else 0
    loops = sum(1 for k in range(2, len(texts)) if texts[k] and texts[k] == texts[k - 1] == texts[k - 2])
    print(f'{a.name}: {len(words)} words over {span:.0f}s, {len(lines)} lines, {fill} filler words kept by Whisper -> {out / a.name}.transcript.txt'
          + (f'\n  WARN the same line repeats {loops + 2}+ times in a row: Whisper may be stuck in a loop there. '
             'Transcribe that stretch again on its own.' if loops else ''))


if __name__ == '__main__':
    main()
