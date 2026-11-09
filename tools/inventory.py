#!/usr/bin/env python3
"""inventory.py - index a footage folder (read-only) into library/: csv, thumbnails, contact sheets (EDIT-WITH-AI.md 5).

Usage: inventory.py FOLDER --tag NAME [--lut file.cube] [--per-sheet 40] [--cols 6]
Writes library/NAME_index.csv (n, path, duration, fps, resolution, date, camera), library/thumbs/NAME_NNN.jpg and
library/NAME_sheet_N.jpg (tile numbers = n in the csv). Never writes into FOLDER. Use --lut for log footage so the
thumbnails show the converted look. Videos only (photos: probe.py lists them).
"""
import argparse
import csv
from pathlib import Path

from common import ROOT
from probe import probe
from sheet import frame, grid

VIDEO = {'.mp4', '.mov', '.m4v', '.mkv', '.mts'}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--lut')
    ap.add_argument('--per-sheet', type=int, default=40)
    ap.add_argument('--cols', type=int, default=6)
    a = ap.parse_args()
    lib = ROOT / 'library'
    (lib / 'thumbs').mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in Path(a.folder).rglob('*') if f.suffix.lower() in VIDEO and not f.name.startswith('.'))
    rows, tiles = [], []
    for i, f in enumerate(files, 1):
        try:
            o = probe(f)
        except Exception as e:
            print(f'skip {f.name}: {e}')
            continue
        v = o.get('video', {})
        rows.append([i, str(f), round(o['duration'], 2), v.get('fps_float', ''), 'x'.join(map(str, v.get('display', []))),
                     (o.get('created') or '')[:19], o.get('camera') or ''])
        th = frame(f, o['duration'] / 2, 320, a.lut)
        th.save(lib / 'thumbs' / f'{a.tag}_{i:03d}.jpg', quality=80)
        tiles.append((th, f'{i} {o["duration"]:.0f}s'))
    with open(lib / f'{a.tag}_index.csv', 'w', newline='', encoding='utf-8') as fh:
        csv.writer(fh).writerows([['n', 'path', 'duration', 'fps', 'resolution', 'date', 'camera']] + rows)
    sheets = 0
    for n in range(0, len(tiles), a.per_sheet):
        sheets += 1
        grid(tiles[n:n + a.per_sheet], a.cols).save(lib / f'{a.tag}_sheet_{sheets}.jpg', quality=82)
    print(f'{len(rows)} clips, {sum(r[2] for r in rows):.0f}s total -> library/{a.tag}_index.csv, {sheets} sheet(s) library/{a.tag}_sheet_N.jpg')


if __name__ == '__main__':
    main()
