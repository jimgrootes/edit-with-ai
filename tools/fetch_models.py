#!/usr/bin/env python3
"""fetch_models.py - download the two models the tools need into tools/models/ (once, at setup).

  Whisper medium (speech to text)   ggml-medium.bin                    1.5 GB   huggingface.co/ggerganov/whisper.cpp
  YuNet (face detection)            face_detection_yunet_2023mar.onnx  232 KB   github.com/opencv/opencv_zoo

Usage: fetch_models.py [--whisper medium] [--check]
  --whisper NAME  a different whisper.cpp model instead of medium: small (466 MB, for computers with 8 GB of memory) or
                  large-v3-turbo (1.6 GB). medium is the one these tools were tested with. transcribe.py uses
                  ggml-medium.bin when it is there, else the first ggml-*.bin in tools/models/.
  --check         only verify the files that are there
Uses curl when it is installed (resumes a broken download; run it again after an interruption), else Python. Checks
size and checksum, and only gives a file its final name once it is complete.
"""
import argparse
import hashlib
import shutil
import subprocess
import urllib.request

from common import MODELS

HF = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin'
KNOWN = {   # name: (bytes, sha1)
    'medium': (1533763059, 'fd9727b6e1217c2f614f9b698455c4ffd82463b4'),
}
YUNET = ('face_detection_yunet_2023mar.onnx',
         'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx',
         232589, 'sha256', '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4')


def problem(path, size=None, algo=None, digest=None, magic=None, minsize=0):
    """None if the file looks right, else what is wrong."""
    n = path.stat().st_size
    if size and n != size:
        return f'{n} bytes, expected {size}'
    if n < minsize:
        return f'only {n} bytes'
    if magic and path.open('rb').read(len(magic)) != magic:
        return 'not a model file (wrong header: an error page?)'
    if digest:
        h = hashlib.new(algo)
        with path.open('rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b''):
                h.update(chunk)
        if h.hexdigest() != digest:
            return f'{algo} checksum does not match'
    return None


def download(url, part):
    curl = shutil.which('curl')
    if curl:
        r = subprocess.run([curl, '-sS', '-L', '--fail', '--retry', '5', '--retry-delay', '3', '-C', '-', '-o', str(part), url])
        if r.returncode:
            raise SystemExit(f'download failed (curl exit {r.returncode}): {url}\nRun this tool again to resume.')
        return
    with urllib.request.urlopen(url) as resp, open(part, 'wb') as fh:     # no resume without curl
        shutil.copyfileobj(resp, fh, 1 << 22)


def get(name, url, check_only, **v):
    dest = MODELS / name
    part = dest.with_name(name + '.part')
    if dest.exists():
        p = problem(dest, **v)
        print(f'ok   {name} ({dest.stat().st_size / 1e6:,.1f} MB)' if not p else f'BAD  {name}: {p} (delete it and run again)')
        return not p
    if check_only:
        print(f'MISSING {name}')
        return False
    if not (part.exists() and v.get('size') and part.stat().st_size == v['size']):
        print(f'downloading {name} from {url.split("/")[2]} ...', flush=True)
        download(url, part)
    p = problem(part, **v)
    if p:
        part.unlink()
        raise SystemExit(f'{name}: downloaded file is wrong ({p}); removed it, run again')
    part.replace(dest)
    print(f'ok   {name} ({dest.stat().st_size / 1e6:,.1f} MB, verified)')
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--whisper', default='medium')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    MODELS.mkdir(parents=True, exist_ok=True)
    size, sha1 = KNOWN.get(a.whisper, (None, None))
    ok = get(f'ggml-{a.whisper}.bin', HF.format(a.whisper), a.check, size=size, algo='sha1' if sha1 else None, digest=sha1,
             magic=b'lmgg', minsize=30_000_000)
    n, url, size, algo, digest = YUNET
    ok &= get(n, url, a.check, size=size, algo=algo, digest=digest)
    print('models ready' if ok else 'models NOT ready')


if __name__ == '__main__':
    main()
