#!/usr/bin/env python3
"""render.py - work/edit.json -> output/vN.mp4 (EDIT-WITH-AI.md 4.5)

Picture and sound are built separately and sample-exact, then muxed, so nothing drifts after a hundred cuts:
  picture  every piece is re-encoded at the output size (16:9 = 1920x1080, 9:16 = 1080x1920) and a constant frame rate
           (the fps filter turns variable-frame-rate phone video into CFR), H.264 High CRF 18, tagged bt709.
           Talking-head pieces are cropped around the face (punch-ins, vertical crops from horizontal footage); b-roll is
           cropped to fill the frame. Log footage (a "lut" on the b-roll or the take) gets its LUT in RGB
           (format=gbrp16le -> lut3d -> back to YUV with out_color_matrix=bt709; without that ffmpeg converts with BT.601
           and the colours shift). Cards are laid on top with a short fade. Pieces are cached by a hash of their settings and joined without re-encoding, so v2 only
           re-encodes what changed.
  sound    the take audio cut per segment with 10 ms fades; music playlist (crossfaded, faded in and out) set "db" LU
           under the voice; two-pass loudnorm to the target with true peak -2.5 dBTP before the AAC encode, because AAC
           adds overshoot (-1.5 on the WAV measured -0.9 dBTP in the file at 192 kbps); AAC 256 kbps. If that misses
           the target by more than 0.8 LU (a voice with very loud peaks), the peaks get a look-ahead limiter first.
Never overwrites: writes the next free vN. Captions: run check.py next, it writes vN.srt from the render itself.

Usage: render.py --project projects/NAME [--edit work/edit.json] [--jobs 3]
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from common import ROOT, key, mmss, rel, run, size_for, timeline

SR = 48000
TP = -2.5                      # aim below -1.5 dBTP: the AAC encode adds overshoot
BT709 = ['-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv']


def face_for(faces, src, t):
    f = faces.get(src) or []
    if not f:
        return 0.5, 0.42
    near = sorted(f, key=lambda d: abs(d['t'] - t))[:3]
    return float(np.median([d['cx'] for d in near])), float(np.median([d['cy'] for d in near]))


def ff_path(p):
    """A path for inside an ffmpeg filter: relative to the workspace when possible (no drive letters, short)."""
    try:
        return Path(os.path.relpath(p, ROOT)).as_posix()
    except ValueError:
        return Path(p).as_posix()


def stamp(p):
    s = Path(p).stat()
    return [s.st_size, s.st_mtime_ns]


def piece_overlays(p, tl):
    res = []
    for o in tl['overlays']:
        lo, hi = max(o['a'], p['start']), min(o['a'] + o['n'], p['start'] + p['frames'])
        if hi > lo:
            res.append({'png': o['png'], 'n': o['n'], 'fade': o.get('fade', 0.25), 'skip': lo - o['a'], 'len': hi - lo,
                        'off': lo - p['start'], 'stamp': stamp(o['png'])})
    return res


def piece_cmd(p, face, fps, W, H, lut, ovs, out):
    A = W / H
    vf = [f'fps={fps}']
    if lut:                                     # log footage -> RGB -> LUT (back to YUV bt709 in the scale below)
        vf += ['scale=in_range=tv:in_color_matrix=bt709', 'format=gbrp16le', f"lut3d=file='{ff_path(lut)}':interp=tetrahedral"]
    if p['kind'] == 'th':
        z, (cx, cy) = p['punch'], face
        vf.append(f"crop=w='trunc(min(iw,ih*{A:.6f})/{z}/2)*2':h='trunc(min(ih,iw/{A:.6f})/{z}/2)*2':"
                  f"x='min(max({cx:.4f}*iw-ow/2,0),iw-ow)':y='min(max({cy:.4f}*ih-oh/2,0),ih-oh)'")
        vf.append(f'scale={W}:{H}:flags=lanczos:out_color_matrix=bt709:out_range=tv')
    else:
        vf += [f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos:out_color_matrix=bt709:out_range=tv',
               f'crop={W}:{H}']
    vf.append('format=yuv420p')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-nostdin', '-ss', f"{max(0.0, p['in'] - 0.5 / fps):.4f}", '-i', p['src']]
    if ovs:
        fc, cur = f"[0:v]{','.join(vf)}[b0]", 'b0'
        for k, o in enumerate(ovs, 1):
            cmd += ['-loop', '1', '-framerate', str(fps), '-t', f"{o['n'] / fps:.4f}", '-i', o['png']]
            d = o['n'] / fps
            F = min(o['fade'], d / 2)
            fade = f',fade=t=in:st=0:d={F:.3f}:alpha=1,fade=t=out:st={d - F:.3f}:d={F:.3f}:alpha=1' if F > 0 else ''
            fc += (f";[{k}:v]format=rgba{fade},trim=start_frame={o['skip']}:end_frame={o['skip'] + o['len']},"
                   f"setpts=PTS-STARTPTS+{o['off'] / fps:.6f}/TB,scale=out_color_matrix=bt709:out_range=tv,format=yuva420p[o{k}];"
                   f"[{cur}][o{k}]overlay=0:0:eof_action=pass:format=yuv420[b{k}]")
            cur = f'b{k}'
        cmd += ['-filter_complex', fc + f';[{cur}]format=yuv420p[v]', '-map', '[v]']
    else:
        cmd += ['-vf', ','.join(vf)]
    return cmd + ['-an', '-frames:v', str(p['frames']), '-r', str(fps), '-fps_mode', 'cfr',
                  '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
                  '-g', str(int(fps * 2)), '-threads', '4', *BT709, '-f', 'mpegts', str(out)]


def load_f32(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                       capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-400:])
    return np.frombuffer(r.stdout, np.float32)


def build_voice(tl, sources):
    spf, fade, cache, parts = SR / tl['fps'], int(0.010 * SR), {}, []
    for s in tl['th']:
        ap = sources[s['src']]['audio']
        if ap not in cache:
            cache[ap] = load_f32(ap)
        a = int(round(s['in'] * SR))
        n = int(round((s['start'] + s['frames']) * spf)) - int(round(s['start'] * spf))
        lead, a = max(0, -a), max(a, 0)                      # a segment may start before the recording began
        seg = np.pad(cache[ap][a:a + n - lead], (lead, 0))
        if len(seg) < n:
            seg = np.pad(seg, (0, n - len(seg)))
        seg[:fade] *= np.linspace(0, 1, fade, endpoint=False, dtype=np.float32)
        seg[-fade:] *= np.linspace(1, 0, fade, endpoint=False, dtype=np.float32)
        parts.append(seg)
    return np.concatenate(parts)


def loudnorm_json(path, target):
    r = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-af',
                        f'loudnorm=I={target}:TP={TP}:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True)
    j, out = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S).group(0)), {}
    for k, v in j.items():
        try:
            out[k] = float(v)
        except ValueError:
            pass                                    # e.g. "normalization_type": "dynamic"
    return out


def normalize(src, L, tgt, out):
    """Second loudnorm pass with the measured values. linear=true keeps the dynamics when the peaks allow it; ffmpeg
    switches to its dynamic mode by itself when they don't (that is what usually happens with a raw voice)."""
    run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-i', src, '-af',
         f"loudnorm=I={tgt}:TP={TP}:LRA=11:measured_I={L['input_i']}:measured_TP={L['input_tp']}:measured_LRA={L['input_lra']}"
         f":measured_thresh={L['input_thresh']}:offset={L['target_offset']}:linear=true",
         '-ar', str(SR), '-c:a', 'pcm_s24le', out])


def music_bed(files, total, out, fade_in=2.0, fade_out=5.0, xf=4.0):
    durs = {f: float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).stdout) for f in set(files)}
    seq, acc = [], 0.0
    while acc < total + 2 * xf and len(seq) < 40:
        f = files[len(seq) % len(files)]
        acc += durs[f] - (xf if seq else 0)
        seq.append(f)
    cmd = ['ffmpeg', '-y', '-v', 'error', '-nostdin']
    for f in seq:
        cmd += ['-i', f]
    fc, prev = '', '[0:a]'
    for k in range(1, len(seq)):
        fc += f'{prev}[{k}:a]acrossfade=d={xf}:c1=tri:c2=tri[x{k}];'
        prev = f'[x{k}]'
    fc += (f'{prev}aresample={SR},aformat=channel_layouts=stereo,atrim=0:{total:.3f},'
           f'afade=t=in:d={fade_in},afade=t=out:st={max(0.0, total - fade_out):.3f}:d={fade_out}[m]')
    run(cmd + ['-filter_complex', fc, '-map', '[m]', '-c:a', 'pcm_s24le', out])
    return len(seq)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', required=True)
    ap.add_argument('--edit')
    ap.add_argument('--jobs', type=int, default=3, help='pieces encoded at the same time (lower it on a busy or small computer)')
    a = ap.parse_args()
    proj = Path(a.project) if Path(a.project).is_absolute() else ROOT / a.project
    work, outd = proj / 'work', proj / 'output'
    edit_path = Path(a.edit) if a.edit else work / 'edit.json'
    edit = json.load(open(edit_path, encoding='utf-8'))
    fps, tl = edit.get('fps', 30), timeline(edit)
    W, H = size_for(edit.get('format', '16:9'))
    missing = sorted({p['src'] for p in tl['pieces'] if not Path(p['src']).exists()})
    if missing:
        raise SystemExit('source file(s) not found (drive not connected?):\n  ' + '\n  '.join(missing))
    need, free = tl['total'] / fps * 6e6, shutil.disk_usage(work).free
    if free < need:
        print(f'WARN only {free / 1e9:.1f} GB free; this render may need up to {need / 1e9:.1f} GB (cache + sound + output)')
    faces = json.load(open(work / 'faces.json')) if (work / 'faces.json').exists() else {}
    cache = work / 'cache'
    cache.mkdir(exist_ok=True)
    outd.mkdir(exist_ok=True)
    t0 = time.time()
    jobs, files = [], []
    for p in tl['pieces']:
        lut = p.get('lut')
        lut = str(ROOT / lut) if lut and not Path(lut).is_absolute() else lut
        face = face_for(faces, p['src'], p['in']) if p['kind'] == 'th' else None
        ovs = piece_overlays(p, tl)
        f = cache / (key(p['kind'], p['src'], round(p['in'], 4), p['frames'], p.get('punch'), face, lut, W, H, fps, ovs, 'r2') + '.ts')
        files.append((f, p['frames']))
        if not f.exists():
            jobs.append((piece_cmd(p, face, fps, W, H, lut, ovs, str(f) + '.part'), f))

    def do(j):
        r = subprocess.run(j[0], capture_output=True, text=True, cwd=ROOT)
        if r.returncode:
            raise RuntimeError(Path(j[1]).name + '\n' + ' '.join(j[0])[:600] + '\n' + r.stderr[-700:])
        Path(str(j[1]) + '.part').replace(j[1])
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(do, jobs))
    t1 = time.time()
    voice = build_voice(tl, edit['sources'])
    total = len(voice) / SR
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'pcm_s24le',
                    str(work / 'voice.wav')], input=voice.tobytes(), capture_output=True, check=True)
    run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-i', work / 'voice.wav', '-af', 'pan=stereo|c0=c0|c1=c0',
         '-c:a', 'pcm_s24le', work / 'mix.wav'])                    # dual-mono, the way it will play
    mix = work / 'mix.wav'
    info = 'no music'
    m = edit.get('music')
    if m:
        fl = m.get('files') or [m['file']]
        files_m = [str(ROOT / f) if not Path(f).is_absolute() else f for f in fl]
        n_tr = music_bed(files_m, total, work / 'bed.wav', m.get('fade_in', 2.0), m.get('fade_out', 5.0))
        vi, bi = loudnorm_json(work / 'voice.wav', -14)['input_i'], loudnorm_json(work / 'bed.wav', -14)['input_i']
        vi += 3.01                                           # mono voice is mixed as dual-mono: BS.1770 reads that 3 LU louder
        gain = vi - m.get('db', 21) - bi
        run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-i', work / 'voice.wav', '-i', work / 'bed.wav', '-filter_complex',
             f'[0:a]pan=stereo|c0=c0|c1=c0[v];[1:a]volume={gain:.2f}dB[m];[v][m]amix=inputs=2:duration=first:normalize=0[o]',
             '-map', '[o]', '-c:a', 'pcm_s24le', work / 'mix.wav'])
        info = f'music {n_tr} track(s), {m.get("db", 21)} LU under the voice'
    tgt = edit['loudness']
    L = L0 = loudnorm_json(mix, tgt)
    normalize(mix, L, tgt, work / 'final.wav')
    got = loudnorm_json(work / 'final.wav', tgt)['input_i']
    if abs(got - tgt) > 0.8:               # peaks too high for the target (phone mics: quiet voice, loud clicks):
        gain = tgt - L['input_i']          # gain first, then a look-ahead limiter on the peaks, then normalize again
        run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-i', mix, '-af',
             f'aformat=sample_fmts=dbl,volume={gain:.2f}dB,alimiter=limit={10 ** ((TP - 1) / 20):.4f}:attack=2:release=60:level=disabled',
             '-c:a', 'pcm_s24le', work / 'limited.wav'])
        L = loudnorm_json(work / 'limited.wav', tgt)
        normalize(work / 'limited.wav', L, tgt, work / 'final.wav')
        info += f', peaks limited ({got:.1f} LUFS without)'
    esc = lambda p: str(p).replace("'", "'\\''")
    (work / 'concat.txt').write_text(''.join(f"file '{esc(f)}'\nduration {n / fps:.6f}\n" for f, n in files))
    n = 1
    while (outd / f'v{n}.mp4').exists():
        n += 1
    mp4 = outd / f'v{n}.mp4'
    part = outd / f'v{n}.part.mp4'
    run(['ffmpeg', '-y', '-v', 'error', '-nostdin', '-f', 'concat', '-safe', '0', '-i', work / 'concat.txt', '-i', work / 'final.wav',
         '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-ar', str(SR), '-ac', '2',
         '-movflags', '+faststart', *BT709, part])
    part.replace(mp4)
    mb = mp4.stat().st_size / 1e6
    print(f"{rel(mp4)}  {total:.1f}s ({mmss(total)})  {W}x{H} {fps} fps  {tl['total']} frames  {mb:.0f} MB | "
          f"{len(files)} picture pieces ({len(jobs)} encoded, {len(files) - len(jobs)} from cache) | "
          f"{len(tl['overlays'])} card(s) | {info} | {L0['input_i']:.1f} LUFS before loudnorm | "
          f"picture {t1 - t0:.0f}s, sound+mux {time.time() - t1:.0f}s\n"
          f"next: check.py {rel(mp4)} --project {rel(proj)}   (QC + v{n}.srt)")


if __name__ == '__main__':
    main()
