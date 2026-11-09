#!/usr/bin/env python3
"""probe.py - what is this file?

One short line per media file: size, duration, displayed resolution (after rotation), fps as a fraction, codec, audio,
colour tags, creation time, camera. Flags HDR footage (HLG/PQ): the tools make SDR (bt709) video and have no HDR
tone mapping, so HDR clips look flat and washed out. Record in SDR (iPhone: Settings > Camera > Record Video > HDR
Video off) or convert them first.

Usage:
  probe.py PATH [PATH ...]   files or folders (folders are searched read-only)
  probe.py --json PATH       full summary as JSON
Import:  from probe import probe   ->  dict
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

EXT = {'.mp4', '.mov', '.m4v', '.mkv', '.mts', '.wav', '.mp3', '.m4a', '.flac', '.aac',
       '.jpg', '.jpeg', '.png', '.heic', '.dng'}
HDR = {'arib-std-b67': 'HLG', 'smpte2084': 'PQ'}


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:200] or f'ffprobe failed on {path}')
    j = json.loads(r.stdout)
    fmt = j.get('format', {})
    st = j.get('streams', [])
    v = next((s for s in st if s['codec_type'] == 'video' and not s.get('disposition', {}).get('attached_pic')), None)
    a = next((s for s in st if s['codec_type'] == 'audio'), None)
    tags = {k.lower(): val for k, val in fmt.get('tags', {}).items()}
    o = {'path': str(path), 'mb': round(int(fmt.get('size', 0)) / 1e6, 1),
         'duration': float(fmt.get('duration') or 0),
         'created': tags.get('creation_time') or tags.get('com.apple.quicktime.creationdate'),
         'camera': ' '.join(x for x in (tags.get('com.apple.quicktime.make'), tags.get('com.apple.quicktime.model')) if x)
                   or tags.get('encoder') or tags.get('com.apple.quicktime.software')}
    if v:
        rot = 0
        for sd in v.get('side_data_list', []):
            if 'rotation' in sd:
                rot = int(round(float(sd['rotation'])))        # degrees counter-clockwise to apply for display
        if 'rotate' in v.get('tags', {}):
            rot = -int(v['tags']['rotate'])
        w, h = int(v['width']), int(v['height'])
        swap = abs(rot) % 180 == 90
        o['video'] = {'codec': v['codec_name'], 'stored': [w, h], 'rotation': rot,
                      'display': [h, w] if swap else [w, h], 'pix_fmt': v.get('pix_fmt'),
                      'fps': v.get('avg_frame_rate') if v.get('avg_frame_rate') not in (None, '0/0') else v.get('r_frame_rate'),
                      'frames': v.get('nb_frames'), 'bitrate_mbps': round(int(v.get('bit_rate') or 0) / 1e6, 1),
                      'color': [v.get('color_space'), v.get('color_transfer'), v.get('color_primaries'), v.get('color_range')],
                      'hdr': HDR.get(v.get('color_transfer') or ''), 'start': v.get('start_time')}
        n, d = (o['video']['fps'] or '0/1').split('/')
        o['video']['fps_float'] = round(int(n) / int(d), 3) if int(d) else 0
    if a:
        o['audio'] = {'codec': a['codec_name'], 'ch': a['channels'], 'rate': int(a['sample_rate']),
                      'bits': a.get('bits_per_sample') or a.get('bits_per_raw_sample'),
                      'duration': float(a.get('duration') or 0), 'start': a.get('start_time')}
    return o


def line(o):
    s = f"{Path(o['path']).name[:44]:44} {o['mb']:>8.1f}MB {o['duration']:>8.2f}s"
    v, a = o.get('video'), o.get('audio')
    if v:
        s += (f"  {v['display'][0]}x{v['display'][1]}" + (f" (stored {v['stored'][0]}x{v['stored'][1]}, rot {v['rotation']})" if v['rotation'] else '')
              + f"  {v['fps']}={v['fps_float']}fps {v['codec']} {v['pix_fmt']} {'/'.join(str(x) for x in v['color'])}")
        if v['hdr']:
            s += f"  !! HDR ({v['hdr']}): will look washed out, see probe.py --help"
    if a:
        s += f"  | audio {a['codec']} {a['ch']}ch {a['rate']}Hz {a['bits'] or ''}bit"
    if o.get('created'):
        s += f"  | {o['created'][:19]}"
    if o.get('camera'):
        s += f"  | {o['camera']}"
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    files = []
    for p in map(Path, args.paths):
        files += sorted(f for f in p.rglob('*') if f.suffix.lower() in EXT and not f.name.startswith('.')) if p.is_dir() else [p]
    res = []
    for f in files:
        try:
            res.append(probe(f))
        except Exception as e:
            print(f'{f.name}: ERROR {e}', file=sys.stderr)
    if args.json:
        print(json.dumps(res if len(res) != 1 else res[0], indent=1))
    else:
        for o in res:
            print(line(o))


if __name__ == '__main__':
    main()
