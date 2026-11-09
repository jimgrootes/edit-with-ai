# Edit with AI

Let an AI coding agent (Claude Code or OpenAI Codex) edit your talking-head videos.

One file, [`EDIT-WITH-AI.md`](EDIT-WITH-AI.md), that you give to your agent. It installs the tools, builds a small
editing pipeline on your own computer and from then on edits your videos: drop your recordings in a folder, get back a
cut video with captions, b-roll, music and clean sound. You do the final check.

## Quick start

1. Install **Claude Code** (Claude Pro or higher) or **Codex** (ChatGPT Plus or higher).
2. Make an empty folder and put `EDIT-WITH-AI.md` in it.
3. Open your agent in that folder and type: **"Read EDIT-WITH-AI.md and set me up."**

## Two routes

| Route | Monthly | One-time | What it does |
|---|---|---|---|
| **1. Budget** | Claude Pro $20 or ChatGPT Plus $20 | $0 | Full talking-head edits with free tools (ffmpeg, Whisper), no editing program |
| **2. Resolve Studio** | Claude Max $100 (or Pro for light use) | DaVinci Resolve Studio $295 | Route 1 plus work inside Resolve: bins, proxies, timelines, overlays |

Prices before tax, checked 8 November 2026. Buy on the provider's website rather than in an app store.

## What's in the file

- Ground rules that keep your originals safe (read-only sources, numbered versions, ask before deleting).
- Setup for macOS, Windows and Linux.
- The tools the agent builds once: probe, transcribe, render, faces, captions, contact sheets, quality check.
- How it plans a talking-head cut: retakes, silences, fillers, punch-ins, b-roll, editor cues ("Claude, zoom in").
- Footage organizing: an index of every clip with thumbnails, searchable in plain words.
- [`tools/grade.html`](tools/grade.html): grade your (log) footage in the browser with curves, compare before and after,
  and download a `.cube` LUT that the agent applies to all your clips. No editing program needed.
- Working cheaply on the $20 plans.
- Route 2: connecting to DaVinci Resolve Studio, proxies, timelines, overlays, and what to do when the connection fails.

## Made by

Jim Grootes, a Dutch photographer and filmmaker on the road in Southeast Asia.
[jimgrootes.com](https://jimgrootes.com) · YouTube [@JimGrootesUnfiltered](https://www.youtube.com/@JimGrootesUnfiltered)

Not affiliated with Anthropic, OpenAI or Blackmagic Design. MIT license.
