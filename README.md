# Edit with AI

Let an AI coding agent (Claude Code or OpenAI Codex) edit your talking-head videos.

Give this folder to your agent. [`EDIT-WITH-AI.md`](EDIT-WITH-AI.md) tells it how to set up, and [`tools/`](tools/)
holds a small editing pipeline that runs on your own computer: drop your recordings in a folder, get back a cut video
with captions, b-roll, music and clean sound. You do the final check.

## Quick start

1. Install **Claude Code** (Claude Pro or higher) or **Codex** (ChatGPT Plus or higher).
2. Download this folder: **Code > Download ZIP** and unzip it, or `git clone https://github.com/jimgrootes/edit-with-ai video-edits`.
3. Open your agent in that folder and type: **"Read EDIT-WITH-AI.md and set me up."**
4. After setup, start a new session. Then for every video: **"Edit the video in projects/<name>."**

Keep about 15 GB free for setup and a first video.

## Two routes

| Route | Monthly | One-time | What it does |
|---|---|---|---|
| **1. Budget** | Claude Pro $20 or ChatGPT Plus $20 | $0 | Full talking-head edits with free tools (ffmpeg, Whisper), no editing program |
| **2. Resolve Studio** | Claude Max $100 (or Pro for light use) | DaVinci Resolve Studio $295 | Route 1 plus work inside Resolve: bins, proxies, timelines, overlays |

Prices before tax, checked 8 November 2026. Buy on the provider's website rather than in an app store.

## What's in the folder

- `EDIT-WITH-AI.md`: ground rules that keep your originals safe (read-only sources, numbered versions, ask before
  deleting), setup for macOS, Windows and Linux, how the agent plans a cut, working cheaply on the $20 plans, and
  route 2 with DaVinci Resolve Studio.
- `tools/`: the pipeline, in Python with ffmpeg and whisper.cpp:
  - `sync.py` lines up a separate mic recording with your takes; `transcribe.py` turns speech into numbered words.
  - `plan.py` cuts retakes, pauses and "uh"s on the sound itself (never inside a word), with punch-ins and editor cues
    ("Claude, zoom in"); `card.py` makes text cards for cues like "put the prices on screen".
  - `render.py` builds the video: b-roll, your LUT on log footage, music under the voice, -14 LUFS, 16:9 or 9:16.
  - `check.py` checks the result (length, loudness, faces, every word) and writes the captions.
  - `inventory.py` and `sheet.py` index your footage with thumbnails, searchable in plain words.
  - [`grade.html`](tools/grade.html): grade your (log) footage in the browser with curves, compare before and after,
    and download a `.cube` LUT that the tools apply to all your clips. No editing program needed.
- `examples/`: a sample `plan.json` (what the agent writes per video) and `vocab.json` (your language and names).

The models (Whisper 1.5 GB, a face detector 232 KB) are not in the repo; `tools/fetch_models.py` downloads them.

## Changelog

**1.1** (9 November 2026), after a real test: a fresh agent edited a 10-minute talking head on the $20 route with only
version 1.0 of the file.
- The tools come with the repo now (`tools/`). In the test, writing them was two thirds of the cost of the whole edit.
- Separate mic recordings: `sync.py` lines them up with each take, clock drift included.
- Whisper keeps filler words through the whole recording (`--carry-initial-prompt`; without it only the first
  30 seconds), and the tool checks that whisper.cpp really wrote a new transcript.
- Cuts come from the sound level, not from Whisper's word times (often hundreds of ms off), and lean towards keeping:
  a filler Whisper isn't sure of stays in. On the test video this kept five words a stricter cut had lost.
- Face detection with YuNet (OpenCV 5 dropped the old Haar cascades); `fetch_models.py` gets both models.
- Editor cues: `card.py` makes text cards and keeps them off the face. Zoom cues step in gradually.
- B-roll is anchored to a word; music is a crossfaded playlist set in LU under the voice; phone video goes to a
  constant frame rate; LUTs convert with the right colour matrix, on b-roll and on log takes.
- Loudness: true peak -2.5 dBTP before the AAC encode at 256 kbps (the encoder adds overshoot); very peaky voices get
  a limiter so -14 LUFS is still reached.
- Captions come from a transcription of the finished render, with a correction list for names (`vocab.json`).
- `check.py`: fixed thresholds, a face check (also: no card over a face), and the places to listen instead of false
  alarms.
- Vertical 9:16 output, cropped around the face.
- Setup ends with a fresh session; at least 15 GB free; honest notes on speed, effort settings and tested platforms.
- `tools/grade.html`: comments in English.

**1.0** (8 November 2026): first version: the setup file, `grade.html` and an example.

## Made by

Jim Grootes, a Dutch photographer and filmmaker on the road in Southeast Asia.
[jimgrootes.com](https://jimgrootes.com) · YouTube [@JimGrootesUnfiltered](https://www.youtube.com/@JimGrootesUnfiltered)

Not affiliated with Anthropic, OpenAI or Blackmagic Design. MIT license.
