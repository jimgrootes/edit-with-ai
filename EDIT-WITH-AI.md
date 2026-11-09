# EDIT-WITH-AI.md

**Let an AI coding agent edit your talking-head videos.** Give this folder to Claude Code or OpenAI Codex and it sets up
a working editing pipeline on your own computer: drop your recordings in a folder, get back a cut video with captions,
b-roll, music and clean sound. You do the final check.

Made by Jim Grootes ([jimgrootes.com](https://jimgrootes.com), YouTube @JimGrootesUnfiltered). Version 1.1, 9 November 2026
(what changed: see README.md).

## How to use this (for humans)

1. Install an agent that can run commands on your computer:
   - **Claude Code** (needs Claude Pro or higher; the free Claude plan doesn't include it), or
   - **Codex** (included with ChatGPT Plus).
2. Get this whole folder, not just this file: on the GitHub page click **Code > Download ZIP** and unzip it, or
   `git clone https://github.com/jimgrootes/edit-with-ai video-edits`. The `tools/` folder holds the editing tools, so
   your agent doesn't have to write them (in our test, writing them was two thirds of the cost).
3. Open your agent in that folder and type: **"Read EDIT-WITH-AI.md and set me up."**
4. Answer its questions. Setup takes 10–20 minutes, most of it downloading (the speech model is 1.5 GB). Keep at least
   **15 GB free** on the drive with this folder.
5. When setup is done, **close the session and start a new one** (a fresh session is much cheaper). From then on every
   video is: **"Edit the video in projects/<name>."** One video per session.

Two routes:

| Route | Monthly | One-time | What the agent can do |
|---|---|---|---|
| **1. Budget** | Claude Pro $20 (or $17/month billed yearly), or ChatGPT Plus $20 | $0 | Full talking-head edits with free tools (ffmpeg, Whisper), no editing program needed |
| **2. Resolve Studio** | Claude Max $100, or Pro if you edit lightly | DaVinci Resolve Studio $295 | Everything in route 1, plus working inside Resolve: bins, proxies, timelines, overlays |

Prices before tax, checked 8 November 2026. Buy subscriptions on the provider's website, not through an app store: the
same plan costs more inside the app. Free DaVinci Resolve 21.1 and later can't be controlled by an agent (external
scripting and Blackmagic's MCP server are Studio-only), which is why route 1 doesn't use Resolve at all.

### What to expect

Tested on 9 November 2026 with a real video: 13 minutes of iPhone takes with a separate clip-on mic, 11 b-roll clips
and three music tracks became a 10:50 first edit: retakes, pauses and most "uh"s out, punch-ins, b-roll with the
camera's LUT, music under the voice, -14 LUFS, captions.
- **Cost:** the edit itself (plan, render, check, two rounds of fixes) used about 172,000 fresh tokens: roughly $2 at
  API list prices with Sonnet. On a $20 plan you pay a flat fee instead; we estimate that edit at roughly a tenth of one
  5-hour Pro session (read from the usage meters of a Max plan, so not measured on Pro itself; at most about a
  seventh). The test spent another $4.53 on having the agent write the tools first. They come with this folder now.
- **Time:** 47 minutes for that edit, about half of it waiting for renders. Section 8 has the details.
- **Result:** about 90% done. You still review: faces in frame, the cards, the feel of the cut. The tools lean towards
  keeping a sound rather than losing a word, so an occasional "uh" stays in.
- **Tested on** macOS (Apple Silicon) with Claude Code. Windows, Linux and Codex are not tested yet; the tools are plain
  Python, ffmpeg and whisper.cpp, and the setup below covers them.

Not affiliated with Anthropic, OpenAI or Blackmagic Design. Use at your own risk; the rules below keep your originals safe.

---

# Instructions for the AI agent

You are setting up a video-editing workspace for the user and will then act as their editor. **The editing tools are
already written**: they are in `tools/` (Python, each with `--help`). Use them; don't rewrite them. Follow the steps in
order. Talk to the user in their own language; keep messages short.

## 0. Ground rules (always, also after setup)

1. **Originals are read-only.** Never move, rename, overwrite or delete the user's footage or its folders. Read it in
   place (plan.json holds the paths). Write only inside this folder.
2. **Never overwrite an output.** Versions count up: `v1.mp4`, `v2.mp4`, ... (render.py does this).
3. **Ask before anything destructive or outward-facing**: deleting the user's files, uploading, publishing, installing
   something system-wide, changing settings in another app, spending money. Your own intermediate files in
   `projects/*/work/` (`cache/`, `*.wav`, `check_*`) you may delete when disk space runs low; old versions in `output/`
   only after asking.
4. **Plan first, then work.** Before a long job, tell the user in two or three lines what you will do and roughly how
   long it takes. Then do it without asking again for every step.
5. **Check your own work before showing it** (`check.py`, 4.10). The user does the final review; your job is to make
   that review short.
6. **Work cheaply** (section 7). Text is cheap, images are expensive, video frames are the most expensive. Read
   transcripts, not footage.

## 1. Ask the user (one message, numbered)

1. Which agent and plan are you on (Claude Pro / Max / other, ChatGPT Plus / Pro)?
2. Your computer: macOS, Windows or Linux? How much free disk space (setup plus one video needs about 15 GB)?
3. Route 1 (no editing program) or route 2 (you have DaVinci Resolve **Studio** 21.1 or newer)?
4. What do you make: horizontal YouTube videos (16:9), vertical shorts/reels (9:16), or both?
5. What language do you speak in your videos? Names or brands you say often (so the captions spell them right)?
6. Your style: captions? Punch-ins (small zooms) to hide cuts? Music under your voice (which licensed tracks)?
7. Where does your footage live (folder or drive), and is there a backup of it?
8. Sound: the camera's own mic, or a separate mic or recorder (lav, wireless mic) that makes its own audio files?
9. Do you film in a log profile (S-Log, D-Log, Apple Log, V-Log...)? With which cameras?

Save the answers in `AGENTS.md` (2.6) so you never ask again.

## 2. Set up (check first, install only what's missing, ask before installing anything system-wide)

1. **This folder:** `EDIT-WITH-AI.md`, `tools/*.py` and `tools/requirements.txt` must be here. If `tools/` is missing,
   the user has only this file: ask them to download the whole folder (step 2 for humans).
2. **ffmpeg + ffprobe** (`ffmpeg -version`). macOS: `brew install ffmpeg` (Homebrew: brew.sh). Windows:
   `winget install Gyan.FFmpeg`. Linux: the package manager (`sudo apt install ffmpeg`). Any recent build works; the
   tools don't need the `subtitles` filter, which many builds lack.
3. **whisper.cpp** (speech to text with word times). Use a recent build: `whisper-cli --help` must list
   `--carry-initial-prompt` and `-dtw`. macOS: `brew install whisper-cpp`. Windows: `whisper-bin-x64.zip` from
   github.com/ggml-org/whisper.cpp/releases, then put `whisper-cli.exe` on the PATH or set `WHISPER_CLI` to it. Linux:
   build it (`git clone https://github.com/ggml-org/whisper.cpp`, `cmake -B build`, `cmake --build build -j --config
   Release`; the binary is `build/bin/whisper-cli`) and set `WHISPER_CLI`.
4. **Python 3.10+ in a virtual environment** in `tools/.venv`:
   `python3 -m venv tools/.venv` and `tools/.venv/bin/pip install -r tools/requirements.txt`
   (Windows: `py -m venv tools\.venv` and `tools\.venv\Scripts\pip install -r tools\requirements.txt`).
   Below, `$P` means `tools/.venv/bin/python` (Windows: `tools\.venv\Scripts\python`). Run everything from this folder.
5. **Models** (not in the repo): `$P tools/fetch_models.py` downloads the Whisper model `ggml-medium.bin` (1.5 GB, from
   huggingface.co/ggerganov/whisper.cpp) and the YuNet face model `face_detection_yunet_2023mar.onnx` (232 KB, from
   github.com/opencv/opencv_zoo) into `tools/models/`, checks them, and resumes a broken download when run again. On a
   computer with 8 GB of memory use `--whisper small` (not tested).
6. **Write `AGENTS.md`** from the template in section 3, a `CLAUDE.md` with the single line `@AGENTS.md` (Claude Code
   reads CLAUDE.md, Codex reads AGENTS.md), and `vocab.json` (4.3) with the user's language and names.
7. **Smoke test:** `$P tools/probe.py <one of the user's clips>`. If the line says HDR, tell the user (4.1).
8. **Finish:** tell the user setup is done and to **start a new session** for the first video. Everything in this
   session's context is paid for again with every message; a fresh session starts small.

## 3. The workspace

```
video-edits/                 this folder
  EDIT-WITH-AI.md            this file (reference; don't re-read it every session)
  AGENTS.md, CLAUDE.md       rules + the user's answers (short! loaded every session)
  vocab.json                 language, filler prompt, name corrections (4.3)
  tools/                     the tools, tools/.venv, tools/models, grade.html
  examples/                  plan.example.json, vocab.example.json
  library/                   footage index, thumbnails, contact sheets (section 5)
  assets/                    luts/, music/ (licensed by the user), fonts/, logo
  projects/
    2026-11-08-my-video/
      input/                 a note with the paths of the recordings (or the recordings)
      work/                  transcripts, plan.json, edit.json, cards/, cache/
      output/                v1.mp4, v1.srt, v1_sheet.jpg, ...
```

`AGENTS.md`, filled in, under 40 lines (it is loaded in every session and costs usage):

```
# AGENTS.md - video edits (read every session, keep it short)

## Rules
1. Originals are read-only: never move, rename, overwrite or delete the user's footage. Write only in this folder.
2. Never overwrite an output (v1.mp4, v2.mp4, ...).
3. Ask before anything destructive or outward-facing. Own intermediate files in projects/*/work/ may go when disk is low.
4. Plan first (2-3 lines: what + how long), then work without asking per step.
5. Check your work with tools/check.py before showing it. The user does the final review.
6. Work cheaply: transcripts, not footage; no whole JSON or transcripts in the chat; one video per session.
Details: EDIT-WITH-AI.md (sections 4 and 6). Don't rewrite the tools.

## The user
- Agent/plan: ...  Computer: ...  Route: 1
- Makes: 16:9 YouTube | 9:16 shorts.  Language: en (vocab.json)
- Style: captions SRT | punch-ins 1.12 | music db 21 | loudness -14
- Footage: ...  Backup: ...
- Sound: camera mic | separate mic (sync.py)
- Cameras: ... (log -> assets/luts/....cube) | phone (no LUT)
- Music (licensed): assets/music/   Font: assets/fonts/...
- Lasting preferences: ...

## Commands (P = tools/.venv/bin/python, PW = projects/<name>/work)
$P tools/probe.py <files|folder>
$P tools/sync.py <recording.wav> --take NAME=<take> ... --outdir $PW        (separate mic only)
$P tools/transcribe.py <$PW/NAME.lav.wav | take> --name NAME --outdir $PW
$P tools/words.py $PW/NAME.words.json 120-160   |   --find "phrase"
$P tools/faces.py <takes> --out $PW/faces.json
$P tools/card.py --out $PW/cards/x.png --title "..." --line "a|b" --faces $PW/faces.json --take <take> --preview <take>@<s>
write $PW/plan.json (examples/plan.example.json), then $P tools/plan.py projects/<name>
$P tools/render.py --project projects/<name>
$P tools/check.py projects/<name>/output/vN.mp4 --project projects/<name>
$P tools/inventory.py <folder> --tag NAME [--lut x.cube]   |   $P tools/sheet.py <video> --every 20 --out x.jpg
```

## 4. The tools

| Tool | What it does |
|---|---|
| `probe.py` | one line per media file: duration, size, fps, codec, rotation, colour, camera; flags HDR |
| `sync.py` | lines up a separate mic recording with each take, clock drift included → `work/NAME.lav.wav` |
| `transcribe.py` | Whisper → `NAME.words.json` (numbered words, times, confidence) + `NAME.transcript.txt` |
| `words.py` | exact word numbers for a range, or where a phrase is said |
| `faces.py` | where the face is in each take (YuNet), for punch-ins, vertical crops and cards |
| `plan.py` | your `plan.json` (which words to keep, cues, b-roll, music) → frame-exact `edit.json` |
| `card.py` | a text card as a transparent PNG, for editor cues ("put the prices on screen") |
| `render.py` | `edit.json` → `output/vN.mp4` |
| `check.py` | quality control of a render, its captions `vN.srt`, and a contact sheet |
| `captions.py` | the captions (check.py runs it) |
| `sheet.py`, `inventory.py` | contact sheets; an index of a footage folder (section 5) |
| `fetch_models.py` | downloads and checks the two models |
| `grade.html` | colour grading in the browser → a `.cube` LUT (4.9) |

If a tool fails, read the error and fix the cause (a path, a missing file). If it is a bug in the tool, fix it in place,
keep the fix small, and tell the user. What the tools already take care of:

### 4.1 Footage: probe.py
- Phone video often has a variable frame rate (29.99 fps) and a rotation tag. render.py turns everything into a
  constant frame rate with the `fps` filter and respects the rotation.
- **HDR** (the iPhone's default "HDR Video", HLG or Dolby Vision) comes out flat and washed out: the tools make SDR
  video and have no tone mapping. Tell the user to switch it off for the next shoot (iPhone: Settings > Camera > Record
  Video > HDR Video). For clips already shot in HDR, ask before trying a conversion.

### 4.2 Sound from a separate mic: sync.py
If the user records sound separately (lav, wireless mic with its own recording, field recorder), that recording is the
sound of the video and the camera's audio is only used to find the sync point.
`sync.py RECORDING --take NAME=TAKE ...` finds each take inside the recording (cross-correlation at 5 points, which
also measures clock drift) and writes `work/NAME.lav.wav` at the take's exact length. Read its line per take:
confidence 70–200 is a clean match; under 15, or a WARN, means listen first. One recording per run (run it again for a
second file). Without a separate mic, skip this: plan.py uses the camera's audio.

### 4.3 Words: transcribe.py and vocab.json
- Transcribe each take's sound: `work/NAME.lav.wav` after sync.py, otherwise the video file. Give each take one short
  NAME and use it everywhere (sync, transcribe, plan.json).
- Whisper drops filler words unless its prompt contains fillers, and whisper.cpp uses a prompt only for the first 30 s
  unless `--carry-initial-prompt` is passed (test: 0 fillers found in 12 minutes without it, 13 with it). The tool does
  both. Don't add names to the prompt: in testing that made Whisper drop every filler and the first seconds of speech.
- whisper-cli exits with code 0 on an unknown flag and writes nothing; the tool removes the old JSON first and stops if
  no new one appears, so a stale transcript never passes as new.
- Word times are rough (some more than 1 s off). Never cut on them: plan.py cuts on the audio (4.4).
- `vocab.json` in this folder (example: `examples/vocab.example.json`): `lang` (Whisper language code), `prompt` (a short
  sentence with the fillers of that language; default "Umm, uh, so, like, okay."), `fillers` (extra filler words for
  that language; only sounds that are never real words), `fix` (corrections for names Whisper gets wrong, for
  example `{"cloud": "Claude"}`; an all-lowercase key matches any case, a key with a capital only that spelling).
  Captions and check.py use `fix`. Add a correction whenever you see a name go wrong.
- Read `NAME.transcript.txt` to plan: one line per sentence, `[mm:ss.s #n]` = time and number of its first word.
  `words.py work/NAME.words.json 120-160` shows exact word numbers; `--find "phrase"` finds a phrase.

### 4.4 The cut: plan.json → plan.py
You decide what stays; plan.py does the exact cutting. Write `work/plan.json` (example: `examples/plan.example.json`):
- `takes`: per take the full path `src` and `keep`, ranges of word numbers `[first, last]`. **Retakes:** when a sentence
  is started more than once, keep the last complete version. Leave out false starts, "let me do that again" and
  off-topic talk. Add `lut` to a take filmed in log (4.9).
- `order`: the takes in playing order. `format` "16:9" or "9:16", `fps` (the camera's rate: 30, 25, 24 or 60),
  `loudness` (-14 for YouTube and Instagram), `punch` (1.12; 1.0 = no punch-ins).
- `zoom` and `cards` (4.5), `broll` and `music` (4.6).

plan.py then works on the sound, not on word times: it finds the voiced stretches, assigns Whisper's words to them in
order, cuts pauses longer than 0.4 s down to 0.15 s of air on each side, removes filler words and stray noises between
words, and puts every cut in silence. It leans towards keeping: a filler glued to a word ("uh-so"), or one Whisper
isn't sure of, stays in, and loud sounds are treated as words, because a lost word is worse than an extra "uh" (on the
test video this kept five words that a stricter version cut). Punch-ins alternate 1.0 / 1.12 between segments, centred
on the face, so the jump cuts look intended.

### 4.5 Editor cues
If the speaker talks to the editor in the recording ("Claude, zoom in a little", "Codex, put the prices on screen",
"end the video with..."), treat it as an instruction at that moment. Keep the cue line in the video unless the user
says otherwise; it's fun to watch the edit answer.
- **Zoom:** `"zoom": [{"take": "main", "from": 51, "to": 70, "zoom": 1.25}]` steps the segments over those words up to
  that zoom.
- **Cards** (a title, prices, a short list, an end card): make the PNG with `card.py` (title plus lines; `"label|value"`
  puts the value on the right; `--side auto` keeps it off the face; `--preview TAKE@SECONDS` writes one image to check
  it), then add `"cards": [{"png": "work/cards/prices.png", "at": ["main", 130], "dur": 5}]`. `at` is the word where it
  appears, or seconds on the output, or `"end"` for the last `dur` seconds. Look at the preview, not at the PNG; check.py
  also warns when a card covers the face. Use the user's font if they have one (`assets/fonts/`).
- Cues the tools can't do (animations, screen recordings): tell the user what you skipped and where.

### 4.6 B-roll and music
- **B-roll** covers the picture while the voice keeps running: `"broll": [{"clip": PATH, "in": 1.0, "dur": 3.5,
  "at": ["main", 412], "lut": "assets/luts/x.cube"}]`. `at` = the word where it starts (2–5 s per insert, where the
  sentence names something visual), `in` = where to start inside the clip (skip shaky first frames). Inserts can't
  overlap or run past the end. Choose clips by file name and contact sheet (section 5), never by opening every clip.
- **Music:** `"music": {"files": [...], "db": 21}`. The tracks play as a playlist with 4 s crossfades, looped if the
  video is longer, faded in and out. `db` = how many LU the music sits **under the voice** (18 louder, 24 softer),
  measured with BS.1770; render.py corrects for the voice being mono. Only music the user has licensed.

### 4.7 Rendering: render.py
- Every piece is re-encoded (never stream-copy cuts: they snap to keyframes and drift) at a constant frame rate (`fps`
  filter), H.264 High CRF 18, tagged bt709, and cached by a hash of its settings: a v2 re-encodes only what changed.
- Picture and sound are built separately and sample-exact, then muxed, so nothing drifts after hundreds of cuts.
  Every sound cut gets a 10 ms fade.
- **Colour:** a LUT on log footage is applied in RGB, `scale=in_range=tv:in_color_matrix=bt709,format=gbrp16le,lut3d=...`,
  and converted back with `scale=...:out_color_matrix=bt709:out_range=tv`. Without that explicit matrix ffmpeg uses
  BT.601 for RGB to YUV and the colours shift.
- **Loudness:** two-pass `loudnorm` to the target with true peak -2.5 dBTP **before** the AAC encode, and AAC at 256
  kbps, because the encoder adds overshoot (test: -1.5 dBTP on the WAV became -0.9 in the file at 192 kbps). A voice
  with very loud peaks (phone mics) first gets a look-ahead limiter, so the target is still reached.
- Output `output/vN.mp4` (the next free number): 1920x1080 for 16:9, 1080x1920 for 9:16 (cropped around the face from
  horizontal footage), 48 kHz stereo. Cards come with a short fade.

### 4.8 Captions
check.py writes `output/vN.srt` from a new transcription of the **rendered** video. Those words are already on the
final timeline, so words right next to a cut stay in (in the test, captions from the source transcript started on
speech 90% of the time, captions from the render 95%). 1–2 lines, max 32 characters per line (18 for vertical), at
least 0.7 s on screen, `fix` corrections applied, no fillers. The SRT is for uploading (YouTube: Subtitles). The tools
don't burn captions into the picture; if the user wants that (shorts), tell them and offer to add it as PNG overlays
the way card.py works (many ffmpeg builds lack the `subtitles` filter).

### 4.9 Colour without DaVinci: tools/grade.html
Log footage (D-Log, S-Log, Apple Log, V-Log...) looks flat until it's converted, and even converted footage often needs
a little more contrast. On route 1 the user grades in the browser, not in an editing program:
1. Tell the user to open `tools/grade.html` (double-click; it works offline in Chrome or Safari), drop in a frame or a
   short clip, and load their camera maker's official "log to Rec.709" LUT as the conversion (download it from the
   maker's site; if they film in a normal colour profile, skip it).
2. They bend the curves (and optionally exposure, contrast, saturation, warmth, or a look LUT they own), compare before
   and after with the wipe, watch the waveform, and click **Download LUT**. That `.cube` contains the conversion plus
   their adjustments.
3. Put it in `assets/luts/` and use it as `"lut"` on the b-roll and on takes from that camera in plan.json. Note the LUT
   per camera in AGENTS.md so every next video uses it. `sheet.py --clips ... --lut x.cube` shows clips with it.
Don't invent a look yourself or "fix" the user's grade; the grade is their taste. If a shot is clearly over- or
underexposed compared to the rest, tell them, and let them adjust it in the tool.

### 4.10 Quality control: check.py
Run it on every version before you show it. One line per check:

| Check | PASS when |
|---|---|
| length | within 0.1 s of edit.json |
| picture | the size and fps of edit.json, colour tags bt709 |
| loudness | within ±1 LU of the target, true peak at most -1.0 dBTP |
| black | no black stretch of 0.1 s or longer |
| faces | a face on every sampled talking-head frame, not cut off by the edge, and no card over it |
| words | a new transcription of the render matches the words the edit should contain for 93% or more |

The word check can't prove that a word is clipped: quiet short words are often "missed" while they are there. Below
93%, the listed times are places to **listen** (tell the user, or transcribe that stretch on its own); below 85%
something structural is wrong (wrong take, bad sync, missing piece). It also lists the fillers it still hears. Then
look at the contact sheet `vN_sheet.jpg` once: faces in frame, cards off the face, b-roll where you meant it.

## 5. Organize footage (the biggest time saver)

When the user asks "what do I have of X", or before a project with a lot of b-roll:
1. `inventory.py <folder> --tag NAME [--lut x.cube]` walks the folder read-only and writes `library/NAME_index.csv`
   (path, duration, fps, resolution, date, camera), a thumbnail per clip and contact sheets of 40 clips. Use the LUT
   for log footage so the thumbnails look right.
2. Optionally describe each sheet in a few words per clip (place, light, subject, shot type) into
   `library/captions.json`. This costs usage (images): do it in batches, and only for folders the user edits from.
3. Searching = matching words in the csv and captions.json, then showing the user one contact sheet of the hits.

Also gather everything for one video in one place: the paths of clips, photos and audio in `input/`, sorted by time.

## 6. The edit, step by step

When the user says "edit projects/<name>" (or points you at recordings):
1. Make the project folder and note the recordings' paths in `input/`. Probe them; tell the user in one line what you
   found (takes, lengths, sound, b-roll).
2. Separate mic → `sync.py`. Otherwise skip.
3. Transcribe every take. Short takes are usually tests or false starts: their transcript tells you.
4. `faces.py` on the takes (for punch-ins, 9:16 and cards).
5. Read the transcripts and write `work/plan.json`: keep ranges (retakes!), cues, b-roll, music. For a first edit with a
   new user, show a one-paragraph summary of the plan first. Run `plan.py` and read its summary.
6. Cards for the cues: `card.py` with `--preview`; look at the previews.
7. `render.py` → `output/v1.mp4`. Say how long it will take (section 8); run it in the background if you can.
8. `check.py` → PASS/WARN, `v1.srt`, contact sheet. Fix what you can (a word cut off: widen the keep range; a card over
   the face: other side) and render v2.
9. Report: path, length, what you cut, and what the user should check, with times ("1:53 price card", "2:24 listen:
   'you' may be clipped", "'uh' left at 0:48 and 3:53").

The user reviews. Their notes become the next version, which is quick: only the changed pieces render again. If a note
is a lasting preference ("never cut my laughs"), add it to `AGENTS.md`.

## 7. Work cheaply (important on the $20 plans)

- Work from the transcript; look at a contact sheet or preview only to check, never at every frame.
- Use the tools; don't rewrite them. They print summaries: never paste a whole JSON or transcript into the chat.
- **A fresh session after setup, and one video per session.** In the test, setup and edit in one session grew the
  context to 477,000 tokens, and every message reads all of it again.
- Thinking is most of the cost: in the test, 77% of the output was the model thinking. For routine edits use a
  smaller model and lower effort: in Claude Code `/model` (Sonnet) and `/effort low` (medium if the cut gets sloppy);
  in Codex, `/model` with a low reasoning effort.
- If the plan's usage limit is close, finish the current render and stop at a clean point instead of starting a step.

## 8. Speed and disk space

- **Disk:** keep at least 15 GB free. The speech model is 1.5 GB; a 10-minute video takes about 1 GB per version, 1 GB of
  cached pieces and 0.7 GB of sound files. render.py warns when space is short. When it runs low, delete your own
  `work/cache/` and `work/*.wav` of finished projects (they can be rebuilt); old versions in `output/` only after
  asking.
- **Speed:** transcribing is quick (13 minutes of audio in about a minute on an Apple Silicon Mac). Rendering is the
  slow part: 4K phone video to a 1080p edit took about 6 minutes per 10 minutes of video on an M4 Max, longer on a
  smaller computer and much longer when the computer is busy (18 minutes in the test, next to another render). Use
  `--jobs 1` or `2` on a small computer. A v2 is quick: unchanged pieces come from the cache (test: a fix round in
  1–2 minutes).
- **Tested on:** macOS 27, Apple Silicon (M4 Max, 36 GB), Python 3.15, numpy 2.5, OpenCV 5.0, Pillow 13, ffmpeg 9.0.2,
  whisper.cpp 1.9.5, Claude Code with Sonnet. Not tested yet: Windows, Linux, Intel Macs, Codex.

## 9. Route 2: DaVinci Resolve Studio

Use Resolve for what it's good at: the user's own grade and finishing. Your job is the work around it. The tools above
still do the rough cut; Resolve takes over from there.

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

## 10. What this setup can't do (tell the user honestly)

- It gets a talking-head video to about 90%. The user still reviews: faces in frame, text in the right place, the feel
  of the cut.
- A filler glued to a word ("uh-so") can't be cut cleanly, and a quiet short word next to a pause can still get lost:
  check.py lists the places to listen.
- Cards are simple text panels. Animated graphics, screen recordings and burned-in captions are not built in.
- Cinematic b-roll edits with complex effects need a human editor; the agent can support (organizing, proxies, rough
  assembly) but not take over.
- Music must be licensed by the user. Don't download music or footage from the internet without the user's say-so.

---

Questions, or a video you made with this? Find me at [jimgrootes.com](https://jimgrootes.com).
License: MIT (see LICENSE). Share it, change it, make it yours.
