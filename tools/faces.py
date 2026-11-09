#!/usr/bin/env python3
"""faces.py - where is the face? Samples frames of each take, finds the face with OpenCV's YuNet detector, saves the box.

Usage: faces.py TAKE.MOV [TAKE.MOV ...] [--every 15] [--out work/faces.json]
Output: {take path: [{"t": s, "cx": 0-1, "cy": 0-1, "w": 0-1}, ...]} (face centre and width as a fraction of the frame).
render.py centres punch-ins and vertical (9:16) crops on it; card.py uses it to keep cards off the face.
Prints the median face centre per take. Needs tools/models/face_detection_yunet_2023mar.onnx (tools/fetch_models.py).
(OpenCV 5 dropped the old Haar cascades, so YuNet is the detector here; it also works on OpenCV 4.8+.)
"""
import argparse
import json
import subprocess
from pathlib import Path

from common import MODELS                              # first: it quiets OpenCV's log before cv2 loads
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from probe import probe  # noqa: E402

MODEL = MODELS / 'face_detection_yunet_2023mar.onnx'


def grab(path, t, w=960):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', f'{t:.2f}', '-i', str(path), '-frames:v', '1',
                        '-vf', f'scale={w}:-2', '-f', 'image2pipe', '-c:v', 'png', '-'], capture_output=True)
    return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None


_DET = {}


def detect(img, score=0.7):
    """Largest face in a BGR image -> (x, y, w, h) in pixels, or None."""
    if not MODEL.exists():
        raise SystemExit(f'no face model at {MODEL}: run tools/fetch_models.py first')
    h, w = img.shape[:2]
    if score not in _DET:
        _DET[score] = cv2.FaceDetectorYN.create(str(MODEL), '', (w, h), score)
    det = _DET[score]
    det.setInputSize((w, h))
    _, f = det.detect(img)
    if f is None or not len(f):
        return None
    return tuple(float(v) for v in max(f, key=lambda r: r[2] * r[3])[:4])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('takes', nargs='+')
    ap.add_argument('--every', type=float, default=15, help='seconds between samples (at least 3 samples per take)')
    ap.add_argument('--out', default='work/faces.json')
    a = ap.parse_args()
    out = json.load(open(a.out)) if Path(a.out).exists() else {}
    for path in a.takes:
        dur = probe(path)['duration']
        n = max(3, int(dur // a.every))
        res = []
        for t in (np.linspace(min(2, dur / 4), max(dur - 2, dur * 3 / 4), n) if dur > 4 else [dur / 2]):
            img = grab(path, t)
            if img is None:
                continue
            f = detect(img)
            if f is None:
                continue
            h, w = img.shape[:2]
            x, y, bw, bh = f
            res.append({'t': round(float(t), 1), 'cx': round((x + bw / 2) / w, 4), 'cy': round((y + bh / 2) / h, 4),
                        'w': round(bw / w, 4)})
        out[str(path)] = res
        name = Path(path).name[:28]
        if res:
            print(f"{name}: face found in {len(res)}/{n} frames, median centre "
                  f"({np.median([r['cx'] for r in res]):.3f}, {np.median([r['cy'] for r in res]):.3f}), width {np.median([r['w'] for r in res]):.3f}")
        else:
            print(f"{name}: NO face found (crops will use the centre)")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
