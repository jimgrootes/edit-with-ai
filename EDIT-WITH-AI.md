# EDIT-WITH-AI.md

**Let an AI coding agent edit your talking-head videos.** Give this file to Claude Code or OpenAI Codex and it sets up a
working editing pipeline on your own computer: drop your recordings in a folder, get back a cut video with captions,
b-roll, music and clean sound. You do the final check.

Made by Jim Grootes ([jimgrootes.com](https://jimgrootes.com), YouTube @JimGrootesUnfiltered). Version 1.0, 8 November 2026.

## How to use this file (for humans)

1. Install an agent that can run commands on your computer:
   - **Claude Code** (needs Claude Pro or higher; the free Claude plan doesn't include it), or
   - **Codex** (included with ChatGPT Plus).
2. Make an empty folder, for example `video-edits`, and put this file in it.
3. Open your agent in that folder and type: **"Read EDIT-WITH-AI.md and set me up."**
4. Answer its questions. Setup takes 15–30 minutes, most of it downloading tools.
5. After that, every edit starts with: **"Edit the video in projects/<name>."**

Two routes are described below:

| Route | Monthly | One-time | What the agent can do |
|---|---|---|---|
| **1. Budget** | Claude Pro $20 (or $17/month billed yearly), or ChatGPT Plus $20 | $0 | Full talking-head edits with free tools (ffmpeg, Whisper), no editing program needed |
| **2. Resolve Studio** | Claude Max $100, or Pro if you edit lightly | DaVinci Resolve Studio $295 | Everything in route 1, plus working inside Resolve: bins, proxies, timelines, overlays |

Prices before tax, checked 8 November 2026. Buy subscriptions on the provider's website, not through an app store: the
same plan costs more inside the app. Free DaVinci Resolve 21.1 and later can't be controlled by an agent (external
scripting and Blackmagic's MCP server are Studio-only), which is why route 1 doesn't use Resolve at all.

Not affiliated with Anthropic, OpenAI or Blackmagic Design. Use at your own risk; the rules below keep your originals safe.

---

# Instructions for the AI agent

You are setting up a video-editing workspace for the user and will later act as their editor. Follow these steps in
order. Talk to the user in their own language; keep messages short.

## 0. Ground rules (always, also after setup)

1. **Originals are read-only.** Never move, rename, overwrite or delete the user's source files or folders. Read them in
   place or copy them into the project. Write only inside the workspace.
2. **Never overwrite an output.** Versions count up: `v1.mp4`, `v2.mp4`, ...
3. **Ask before anything destructive or outward-facing**: deleting files, uploading, publishing, changing settings in
   another app, spending money.
4. **Plan first, then work.** Before a long job, tell the user in two or three lines what you will do and roughly how long
   it takes. Then do it without asking again for every step.
5. **Check your own work before showing it** (section 6). The user does the final review; your job is to make that review
   short.
6. **Work cheaply** (section 7). Text is cheap, images are expensive, video frames are the most expensive. Read
   transcripts, not footage.

## 1. Ask the user (one message, numbered)

1. Which agent and plan are you on (Claude Pro / Max / other, ChatGPT Plus / Pro)?
2. Your computer: macOS, Windows or Linux? Roughly how much free disk space?
3. Route 1 (no editing program) or route 2 (you have DaVinci Resolve **Studio** 21.1 or newer)?
4. What do you make: horizontal YouTube videos, vertical shorts/reels, or both?
5. What language do you speak in your videos?
6. Your style: captions on or off? Punch-ins (small zooms) to hide cuts? Music under your voice?
7. Where does your footage live (folder or drive), and is there a backup of it?

Save the answers in `AGENTS.md` (step 3) so you never ask again.

## 2. Install the tools (check first, install only what's missing)

Check each tool with `--version` before installing. Ask before installing anything system-wide.

**All platforms**
- **ffmpeg + ffprobe** (cutting, encoding, loudness). Check that the build has the `subtitles` filter
  (`ffmpeg -filters | grep subtitles`); some builds lack libass. If it's missing, burn captions as PNG overlays instead
  (section 4.6).
- **Python 3.10+** with a virtual environment in `tools/.venv`. Packages: `numpy`, `opencv-python` (face detection,
  contact sheets), `pillow`.

**Transcription with word timestamps**
- **macOS (Apple Silicon):** `whisper.cpp` (`brew install whisper-cpp`) plus a model from
  https://huggingface.co/ggerganov/whisper.cpp (start with `ggml-medium.bin`; `ggml-large-v3-turbo.bin` if the Mac has
  16 GB+ memory). Command:
  `whisper-cli -m <model> -f audio.wav -l <lang> -ojf -of <out>` (`-ojf` = JSON with token timestamps). For tighter word
  timing add `-dtw medium -nfa` (DTW timestamps need flash attention off).
- **Windows / Linux:** `pip install faster-whisper` in the venv;
  `WhisperModel("medium").transcribe(path, language=<lang>, word_timestamps=True)`.
  Uses the GPU if CUDA is present, otherwise CPU (slower but fine).
- Whisper tends to **drop filler words** ("uh", "um"). To catch them, pass an initial prompt that contains fillers
  (for example "Umm, uh, so, like, okay.") and also look for gaps between words longer than ~0.4 s.

**Optional**
- `auto-editor` (`pip install auto-editor`): fast silence cutting, and it can export a timeline file for Resolve, Premiere,
  Final Cut, Kdenlive or Shotcut (`--export resolve`, `--export premiere`, ...). Useful as a first pass; the pipeline
  below does more.
- `exiftool`: metadata for photos.

## 3. Create the workspace

```
video-edits/
  AGENTS.md            rules + the user's answers (short! read every session)
  CLAUDE.md            one line: @AGENTS.md   (Claude Code reads CLAUDE.md, Codex reads AGENTS.md)
  EDIT-WITH-AI.md      this file (reference, don't re-read it every session)
  tools/               the scripts you build once (section 4)
  library/             footage index, thumbnails, contact sheets (section 5)
  assets/              logo, fonts, LUTs, licensed music, sound effects
  projects/
    2026-11-08-my-video/
      input/           the user's recordings for this video (or a note with their paths)
      broll/           b-roll and photos for this video
      work/            transcript, edit.json, renders in progress, cache
      output/          v1.mp4, v1.srt, v1_sheet.jpg, ...
```

Write `AGENTS.md` in under 60 lines: the ground rules from section 0, the user's answers, the paths of their tools and
models, and the one-line commands for each tool you build. Keep it short; it's loaded into every session and costs usage.

## 4. Build the tools (once)

Write each tool as a small Python script in `tools/` with a `--help` and a docstring. Each prints a short summary
(paths, durations, counts), never pages of logs. Test each on a 30-second clip before moving on.

### 4.1 `probe.py`: what is this file
ffprobe JSON → duration, fps (as a fraction), resolution, rotation, codec, audio channels, color tags, creation time,
camera model if present. Vertical phone footage often has a rotation tag: respect it.

### 4.2 `transcribe.py`: words with times
Extract audio (`ffmpeg -i in -vn -ac 1 -ar 16000 -c:a pcm_s16le work/audio.wav`), run Whisper, write
`work/words.json` (`[{"w": "word", "start": s, "end": s}]`) and a readable `work/transcript.txt` with a timestamp at the
start of every sentence. The transcript is what you read when you plan the edit; never read the video for this.

### 4.3 `plan` (you, not a script): `work/edit.json`
Read `transcript.txt` and decide the cut. Write an edit decision list:

```json
{
  "format": "16:9",
  "fps": 25,
  "loudness": -14,
  "segments": [
    {"src": "input/A001.mp4", "in": 12.40, "out": 31.85, "punch": 1.0, "note": "hook"},
    {"src": "input/A001.mp4", "in": 44.10, "out": 58.02, "punch": 1.12},
    {"src": "broll/pool.mp4", "in": 3.0, "dur": 3.5, "over": true, "note": "b-roll over the voice"}
  ],
  "captions": true,
  "music": {"file": "assets/music/track.wav", "db": -22}
}
```

Editing rules for talking heads:
- **Retakes:** when a sentence is started more than once, keep the last complete version.
- **Silences:** remove pauses longer than ~0.4 s; leave 0.10–0.20 s of air before and after speech so it doesn't sound
  clipped.
- **Fillers:** remove "uh/um" unless the user wants a looser feel.
- **Cut points:** snap every in/out to the quietest 50 ms within ±0.25 s of the word boundary (use the audio RMS), so no
  half words or breaths remain at a join.
- **Punch-ins:** alternate 100% and ~110–115% between consecutive talking-head segments to hide jump cuts. Center the
  crop on the face (4.5).
- **B-roll:** 2–5 s per insert, placed over the voice where the sentence names something visual. Pick from `broll/` using
  file names and the contact sheet (section 5), not by opening every clip.
- **Editor cues:** if the speaker addresses the editor by name in the recording ("Claude, zoom in a little", "Codex, put
  the prices on screen"), treat it as an instruction at that moment: zoom in/out, show a title or card, end the video.
  Keep the cue line in the video unless the user says otherwise; it's fun to watch the edit answer.

### 4.4 `render.py`: edit.json → video
- Re-encode; don't stream-copy cuts (copy cuts snap to keyframes and drift).
- Round every duration to whole frames. Build picture and sound separately and sample-exact, then mux, so nothing drifts
  out of sync after a hundred cuts.
- Put a 10 ms fade at both ends of every audio segment to avoid clicks.
- B-roll segments marked `"over": true` replace the picture only; the voice keeps running underneath.
- Music: duck it under the voice (`sidechaincompress`, or a fixed level around -20 to -24 dB), fade in and out.
- Loudness: two-pass `loudnorm` to the target (YouTube/Instagram: -14 LUFS integrated, true peak -1.5 dB).
- Export: H.264 High, CRF 18, `yuv420p`, AAC 48 kHz, tagged bt709 (`-color_primaries bt709 -color_trc bt709
  -colorspace bt709`). 9:16 version: crop around the face from the 16:9 master, or reframe per segment.
- Cache each rendered segment by a hash of its settings, so v2 only re-renders what changed.

### 4.5 `faces.py`: where is the face
OpenCV face detection (YuNet if available, otherwise the Haar cascade) on a few frames per segment. Output the face box
per segment. Use it to center punch-ins and 9:16 crops, and to keep text away from faces.

### 4.6 `captions.py`: subtitles
Build captions from `words.json`, re-timed to the edited timeline: 1–2 lines, max ~32 characters per line (9:16: ~18),
break at natural pauses, minimum 0.7 s on screen. Always write `vN.srt`. Burn in only if the user wants it: with the
`subtitles` filter (ASS styling) if ffmpeg has libass, otherwise render each caption as a transparent PNG with Pillow and
overlay it. Keep captions in the lower third and never over a face.

### 4.7 `sheet.py`: contact sheets
A grid of small frames (for example one per 2 s of output, or one per clip for a footage folder) with timestamps. This is
how you look at video cheaply: one image instead of hundreds of frames.

### 4.8 `check.py`: quality control
- ffprobe the output: duration, streams, fps, resolution, color tags.
- Re-transcribe the output and compare it with the intended script/transcript: every kept sentence complete, no half
  words at the joins, no repeated words from a retake.
- Measure loudness (`loudnorm` in print mode): within ±1 LU of the target.
- Make a contact sheet of the output and look at it once: faces in frame, captions not over faces, no black frames.

### 4.9 Color without DaVinci: `tools/grade.html`
Log footage (D-Log, S-Log, Apple Log, V-Log…) looks flat until it's converted, and even converted footage often needs a
little more contrast. On route 1 the user grades in the browser, not in an editing program:
1. Tell the user to open `tools/grade.html` (double-click; it works offline in Chrome or Safari), drop in a frame or a
   short clip, and load their camera maker's official "log to Rec.709" LUT as the conversion (download it from the
   maker's site; if they film in a normal color profile, skip it).
2. They bend the curves (and optionally exposure, contrast, saturation, warmth, or a look LUT they own), compare before
   and after with the wipe, watch the waveform, and click **Download LUT**. That `.cube` contains the conversion plus
   their adjustments.
3. Put the file in `work/` and apply it in `render.py` to every segment shot on that camera:
   `-vf "lut3d=file=work/<name>.cube"` (on the original log files, before scaling). Store the LUT path per camera in
   `AGENTS.md` so every next video uses it automatically.
Don't invent a look yourself or "fix" the user's grade; the grade is their taste. If a shot is clearly over- or
underexposed compared to the rest, tell them, and let them adjust it in the tool.

## 5. Organize footage (the biggest time saver)

When the user asks "what do I have of X", or before a project with a lot of b-roll:

1. `inventory.py <folder>`: walk the folders read-only, probe every video and photo, write `library/index.csv` (path,
   duration, fps, resolution, date, camera). Skip system folders. Never write into the source.
2. One thumbnail per clip (`library/thumbs/`), then contact sheets of ~40 clips each.
3. Optionally describe each sheet in a few words per clip (place, light, subject, shot type) into
   `library/captions.json`. This costs usage: do it in batches, and only for folders the user actually edits from.
4. Searching = matching words in `index.csv` and `captions.json`, then showing the user one contact sheet of the hits.

Also gather everything for one video in one place: clips, photos, screenshots and audio into the project folder (copies
or a list of paths), sorted by time.

## 6. The edit, step by step

When the user says "edit projects/<name>":

1. Probe all files in `input/` (4.1). Tell the user what you found in one line.
2. Transcribe (4.2).
3. Plan the cut (4.3) and write `edit.json`. For a first edit with a new user, show a one-paragraph summary of the plan.
4. Render `output/v1.mp4` + `v1.srt` (4.4, 4.6).
5. Check (4.8). Fix what you can, re-render as v2 if needed.
6. Report: path, length, what you cut, what the user should look at (for example "check 2:14, the punch-in is tight").

The user reviews. Their notes become the next version. If a note is a lasting preference ("never cut my laughs"),
add it to `AGENTS.md`.

## 7. Work cheaply (important on the $20 plans)

- Work from the transcript; look at a contact sheet only to check, never at every frame.
- Build the tools once and reuse them. Don't rewrite a tool every session.
- One video per session; start a fresh session for the next video.
- Tools print summaries, not full logs. Never paste a whole JSON or transcript back into the chat.
- For routine runs, a smaller and faster model is usually enough (in Claude Code: `/model`).
- If the plan's usage limit is close, finish the current render and stop at a clean point rather than starting a new step.

## 8. Route 2: DaVinci Resolve Studio

Use Resolve for what it's good at: the user's own grade and finishing. Your job is the work around it.

**Requirements:** DaVinci Resolve **Studio** 21.1 or newer, Resolve running, and in Preferences > System > General,
External scripting set to **Local**. Since 21.1, advanced scripting and Blackmagic's MCP server need Studio.

**Connect from Python** (paths from Blackmagic's scripting README, `Developer/Scripting/README.md`):

| OS | RESOLVE_SCRIPT_API | RESOLVE_SCRIPT_LIB |
|---|---|---|
| macOS | `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting` | `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so` |
| Windows | `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting` | `C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll` |
| Linux | `/opt/resolve/Developer/Scripting` | `/opt/resolve/libs/Fusion/fusionscript.so` |

Add `$RESOLVE_SCRIPT_API/Modules` to `PYTHONPATH`, then `import DaVinciResolveScript as dvr; resolve = dvr.scriptapp("Resolve")`.
Read that README and the API stubs before calling functions; don't guess method names.

**Blackmagic's MCP server** ships with Resolve Studio 21.1+ ("Native MCP server for interacting with AI assistants"). If
the user installs it, it gives you a Python sandbox with `resolve` already connected, API search and a changelog. Either
way, prefer **one script per task** over many small calls: it's faster and uses less of the plan.

**Rules inside Resolve**
- Check the project name before acting, and never act during a render.
- Don't restructure the user's timeline. Duplicate it, or add your own tracks on top.
- Don't touch grades, LUTs or color settings unless asked.
- Save the project after scripted changes (`ProjectManager.SaveProject()`), and say what changed.
- To look at a frame: move the playhead, `Project.ExportCurrentFrameAsStill(path)`, then put the playhead back.

**Useful jobs**
- **Import and bins:** import per shoot day into bins; never import the same files twice into different bins without
  telling the user (see proxies).
- **Proxies** (edit on a laptop without the camera or drive connected): per clip render ProRes 422 LT or Proxy at 1080p
  with ffmpeg, with the clip's own start timecode (`GetClipProperty("Start TC")`) and the same frame count and fps. Write
  to `.part.mov`, verify, rename, then `MediaPoolItem.LinkProxyMedia(path)`. A proxy is linked to one media pool item,
  not to the file: if the same clips exist in two bins, link both.
- **Timeline from edit.json:** create a timeline at the right fps/resolution, then `MediaPool.AppendToTimeline` with
  clip info (`mediaPoolItem`, `startFrame`, `endFrame`, `trackIndex`, `recordFrame`, `mediaType`). Check the placed
  length with `GetStart()`/`GetEnd()`; treat `endFrame` as exclusive unless your test shows otherwise.
- **Overlays** (titles, logos, cards): render ProRes 4444 with alpha at the timeline's resolution and fps (straight
  alpha), import, place on a new track above everything (above adjustment clips, so the grade doesn't touch them), and
  check stills: text never over a face.

**If the connection fails**
- `scriptapp()` returns `None`: is it Studio, is Resolve running, is External scripting on Local?
- Resolve listens on port 1144 and answers on a dynamic port in 49152–65535. Another local app (local AI servers are a
  common one) can sit on that range: list listeners (`lsof -nP -iTCP -sTCP:LISTEN` on macOS/Linux,
  `netstat -ano` on Windows), restart that app or restart Resolve.
- Windows: run Python natively, not inside WSL; the scripting library is a Windows DLL.

## 9. What this setup can't do (tell the user honestly)

- It gets a talking-head video to about 90%. The user still reviews: faces in frame, text in the right place, the
  feel of the cut.
- Cinematic b-roll edits with complex effects need a human editor; the agent can support (organizing, proxies, rough
  assembly) but not take over.
- Music must be licensed by the user. Don't download music or footage from the internet without the user's say-so.

---

Questions, or a video you made with this? Find me at [jimgrootes.com](https://jimgrootes.com).
License: MIT (see LICENSE). Share it, change it, make it yours.
