#!/usr/bin/env python3
"""sheet.py - contact sheet: lots of small frames with timestamps in ONE image (the cheap way to look at video).

Usage:
  sheet.py VIDEO --every 20 --out sheet.jpg [--cols 6] [--w 320]        one frame every N seconds
  sheet.py --clips A.mp4 B.mp4 ... --out sheet.jpg [--lut file.cube]    the middle frame of each clip (numbered)
--lut shows log footage converted (same colour path as render.py).
"""
import argparse
import io
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from probe import probe


def frame(path, t, w=320, lut=None):
    vf = []
    if lut:
        lut = Path(lut).as_posix()
        vf += ['scale=in_range=tv:in_color_matrix=bt709', 'format=gbrp16le', f"lut3d=file='{lut}':interp=tetrahedral"]
    vf.append(f'scale={w}:-2:flags=bicubic')
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', f'{t:.3f}', '-i', str(path), '-frames:v', '1',
                        '-vf', ','.join(vf), '-f', 'image2pipe', '-c:v', 'png', '-'], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert('RGB') if r.stdout else Image.new('RGB', (w, int(w * 9 / 16)), (60, 0, 0))


def grid(tiles, cols=6, pad=4):
    """tiles = [(PIL image, label)] -> one image."""
    w, h = tiles[0][0].size
    rows = -(-len(tiles) // cols)
    sheet = Image.new('RGB', (min(cols, len(tiles)) * (w + pad) + pad, rows * (h + pad) + pad), (18, 18, 18))
    font = ImageFont.load_default(size=14)
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(tiles):
        x, y = pad + (i % cols) * (w + pad), pad + (i // cols) * (h + pad)
        sheet.paste(im.resize((w, h)), (x, y))
        d.rectangle([x, y, x + d.textbbox((0, 0), label, font=font)[2] + 8, y + 18], fill=(0, 0, 0))
        d.text((x + 4, y + 2), label, fill=(255, 220, 120), font=font)
    return sheet


def video_sheet(video, every, out, cols=6, w=320):
    d = probe(video)['duration']
    ts = np.arange(0.5, d - 0.1, every)
    tiles = [(frame(video, t, w), f'{int(t // 60)}:{int(t % 60):02d}') for t in ts]
    grid(tiles, cols).save(out, quality=82)
    return len(tiles)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video', nargs='?')
    ap.add_argument('--clips', nargs='+')
    ap.add_argument('--every', type=float, default=20)
    ap.add_argument('--out', required=True)
    ap.add_argument('--cols', type=int, default=6)
    ap.add_argument('--w', type=int, default=320)
    ap.add_argument('--lut')
    a = ap.parse_args()
    if a.clips:
        tiles = []
        for i, c in enumerate(a.clips, 1):
            d = probe(c)['duration']
            tiles.append((frame(c, d / 2, a.w, a.lut), f'{i} {Path(c).stem[-9:]} {d:.0f}s'))
        grid(tiles, a.cols).save(a.out, quality=82)
        n = len(tiles)
    elif a.video:
        n = video_sheet(a.video, a.every, a.out, a.cols, a.w)
    else:
        ap.error('give a VIDEO or --clips')
    print(f'{n} frames -> {a.out}')


if __name__ == '__main__':
    main()
