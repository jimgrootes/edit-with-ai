#!/usr/bin/env python3
"""words.py - look up word numbers in a take, so plan.json ranges and anchors are exact (counting words by eye in a
transcript line goes wrong easily).

Usage:
  words.py work/NAME.words.json 120-160          the words 120..160 with their number and time
  words.py work/NAME.words.json --find "prices on the screen"   every place that phrase is said (word numbers)
The transcript line `[01:02.3 #120] So let's start ...` means: this line starts with word 120.
"""
import argparse
import json

from common import mmss, norm


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('words')
    ap.add_argument('range', nargs='?', help='FROM-TO, for example 120-160')
    ap.add_argument('--find')
    a = ap.parse_args()
    W = json.load(open(a.words, encoding='utf-8'))
    if a.find:
        q = [norm(x) for x in a.find.split() if norm(x)]
        ws = [norm(w['w']) for w in W]
        hits = [i for i in range(len(W) - len(q) + 1) if ws[i:i + len(q)] == q]
        for i in hits[:20]:
            ctx = ' '.join(w['w'] for w in W[max(0, i - 4):i + len(q) + 4])
            print(f'#{i}-{i + len(q) - 1} at {mmss(W[i]["t"])}: ... {ctx} ...')
        print(f'{len(hits)} hit(s) for "{a.find}"' + (' (showing 20)' if len(hits) > 20 else ''))
        return
    lo, hi = (int(x) for x in a.range.split('-')) if a.range else (0, min(len(W), 60) - 1)
    hi = min(hi, len(W) - 1)
    row = []
    for i in range(max(0, lo), hi + 1):
        row.append(f'#{i} {W[i]["w"]}')
        if len(row) == 10 or i == hi:
            print(f'{mmss(W[i - len(row) + 1]["t"]):>7}  ' + '  '.join(row))
            row = []
    print(f'({len(W)} words in this take, numbers 0..{len(W) - 1})')


if __name__ == '__main__':
    main()
