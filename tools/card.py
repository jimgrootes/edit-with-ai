#!/usr/bin/env python3
"""card.py - a text card (title + lines) as a transparent PNG, for editor cues like "Claude, put the prices on screen".

Usage:
  card.py --out work/cards/prices.png --title "WHAT IT COSTS" --line "Claude Pro|$20 / month" --line "Resolve Studio|$295 once"
          [--format 16:9] [--side auto|left|right|center|bottom] [--faces work/faces.json --take TAKE.MOV]
          [--font assets/fonts/MyFont-Bold.ttf] [--accent "#f2b84b"] [--preview TAKE.MOV@12.5]
A line "label|value" puts the value on the right. The PNG has the size of the output video; reference it in plan.json
"cards" (render.py lays it over the picture with a short fade). --side auto puts the card on the side away from the
face (needs --faces and --take, else left). Vertical formats always put it in the lower part. --preview writes
<out>_preview.jpg: the card over a frame of the take, to check it is not over the face (look at that, not the PNG).
Font: --font, else the first .ttf/.otf in assets/fonts/, else a bold system font, else Pillow's built-in font.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from common import ROOT, size_for

SYSTEM_FONTS = ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/Library/Fonts/Arial Bold.ttf',
                'C:/Windows/Fonts/arialbd.ttf', 'C:/Windows/Fonts/segoeuib.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
                '/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf']


def font_path(arg):
    if arg:
        return arg
    own = sorted(p for p in (ROOT / 'assets' / 'fonts').glob('*') if p.suffix.lower() in ('.ttf', '.otf')) \
        if (ROOT / 'assets' / 'fonts').exists() else []
    bold = [p for p in own if 'bold' in p.name.lower()]
    for p in bold + own + [Path(s) for s in SYSTEM_FONTS]:
        if p.exists():
            return str(p)
    return None


def load(path, size):
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


def face_x(faces, take):
    if not faces or not take:
        return None
    pts = json.load(open(faces)).get(str(take)) or []
    return sorted(p['cx'] for p in pts)[len(pts) // 2] if pts else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title', default='')
    ap.add_argument('--line', action='append', default=[])
    ap.add_argument('--format', default='16:9')
    ap.add_argument('--side', default='auto', choices=['auto', 'left', 'right', 'center', 'bottom'])
    ap.add_argument('--faces')
    ap.add_argument('--take')
    ap.add_argument('--font')
    ap.add_argument('--accent', default='#f2b84b')
    ap.add_argument('--preview', help='TAKE@SECONDS: write <out>_preview.jpg with the card over that frame')
    a = ap.parse_args()
    W, H = size_for(a.format)
    vertical = H > W
    side = a.side
    if vertical and side in ('auto', 'left', 'right'):
        side = 'bottom'
    elif side == 'auto':
        fx = face_x(a.faces, a.take)
        side = 'left' if fx is None or fx >= 0.5 else 'right'
    fp = font_path(a.font)
    unit = min(W, H)
    maxw = {'left': 0.36 * W, 'right': 0.36 * W, 'center': 0.62 * W, 'bottom': 0.86 * W if vertical else 0.7 * W}[side]
    rows = [(l.split('|', 1) + [''])[:2] for l in a.line]
    scale = 1.0
    while True:
        ft, fl = load(fp, int(unit * 0.062 * scale)), load(fp, int(unit * 0.046 * scale))
        pad, gap = int(unit * 0.04 * scale), int(unit * 0.022 * scale)
        d = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
        tw = d.textbbox((0, 0), a.title, font=ft)[2] if a.title else 0
        lw = [d.textbbox((0, 0), l, font=fl)[2] + (int(unit * 0.05) + d.textbbox((0, 0), v, font=fl)[2] if v else 0) for l, v in rows]
        inner = max([tw] + lw)
        if inner + 2 * pad <= maxw or scale < 0.45:
            break
        scale *= 0.92
    th_t = (ft.getbbox('Hg')[3] if a.title else 0)
    th_l = fl.getbbox('Hg')[3]
    pw = int(inner + 2 * pad)
    ph = int(2 * pad + th_t + (gap * 1.4 if a.title and rows else 0) + len(rows) * th_l + max(0, len(rows) - 1) * gap)
    m = int(0.045 * W)
    x = {'left': m, 'right': W - m - pw, 'center': (W - pw) // 2, 'bottom': (W - pw) // 2}[side]
    y = int(0.82 * H) - ph if side == 'bottom' else int(0.46 * H - ph / 2)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = Image.new('L', (W, H), 0)                                  # soft shadow under the panel
    ImageDraw.Draw(sh).rounded_rectangle([x, y + int(unit * 0.01), x + pw, y + ph + int(unit * 0.01)], radius=int(unit * 0.025), fill=150)
    img.putalpha(sh.filter(ImageFilter.GaussianBlur(unit * 0.015)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + pw, y + ph], radius=int(unit * 0.025), fill=(14, 14, 14, 222))
    cy = y + pad
    if a.title:
        d.text((x + pad, cy), a.title, font=ft, fill=a.accent)
        cy += th_t + int(gap * 1.4)
    for l, v in rows:
        d.text((x + pad, cy), l, font=fl, fill=(245, 245, 240, 255))
        if v:
            d.text((x + pw - pad - d.textbbox((0, 0), v, font=fl)[2], cy), v, font=fl, fill=(245, 245, 240, 255))
        cy += th_l + gap
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f'card {W}x{H} -> {out} | panel {side}, x {x}..{x + pw}, y {y}..{y + ph}, font {Path(fp).name if fp else "Pillow default"}'
          + (f', text shrunk to {scale:.0%}' if scale < 1 else ''))
    if a.preview:
        from sheet import frame
        src, t = a.preview.rsplit('@', 1)
        bg = frame(src, float(t), W)
        bw, bh = bg.size
        k = max(W / bw, H / bh)                                      # cover the output frame like render.py does
        bg = bg.resize((int(bw * k + 0.5), int(bh * k + 0.5)))
        fx = face_x(a.faces, a.take or src)
        cx = int((fx if fx is not None else 0.5) * bg.size[0])
        left = min(max(cx - W // 2, 0), bg.size[0] - W)
        top = (bg.size[1] - H) // 2
        bg = bg.crop((left, top, left + W, top + H)).convert('RGBA')
        bg.alpha_composite(img)
        pv = out.with_name(out.stem + '_preview.jpg')
        bg.convert('RGB').resize((W // 2, H // 2)).save(pv, quality=80)
        print(f'preview -> {pv}')


if __name__ == '__main__':
    main()
