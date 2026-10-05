# avatar-service — Alapon, the SyncTalk 2D talking head

**Owner:** Member 1 (Lead). See [plan.md](../plan.md) §6.6.

The real-time talking-head service, running **Alapon** — the lip-sync model from the
`Fydp_v2` project, trained on Redwan's recording (the **`redwan`** dataset, checkpoint
`alapon/59.pth`, epoch 60). The server is Alapon's production one, synced from `Fydp_v2`
on 2026-10-05.

This runs as a **separate process from the LearnQuest backend** — it needs a CUDA GPU
and a conda environment that the FastAPI app does not. The backend talks to it over
HTTP/WebSocket via `AVATAR_SERVICE_URL`.

> **This is the only avatar.** The placeholder SVG avatar was removed on 2026-09-22.
> When `AVATAR_SERVICE_URL` is empty, or this service is down, or no speech provider is
> configured, the app shows an "avatar offline" panel — the tutor still answers in text
> and Teach-Back still runs, there is just no face.

---

## What is here

| Path | What | In git? |
| --- | --- | --- |
| `avatar_server_ws.py` | the WebSocket server — this is the entrypoint | ✅ |
| `unet_328.py`, `utils.py`, `datasetsss_328.py` | model + audio feature code | ✅ |
| `inference_328.py`, `synctalk_server.py` | offline inference / older HTTP server | ✅ |
| `train_328.py`, `syncnet_328.py`, `training_328.sh` | training pipeline | ✅ |
| `data_utils/*.py` | face detection + landmark extraction (preprocessing) | ✅ |
| `data_utils/*.onnx`, `*.pth.tar` | the two preprocessing models, 8 MB | ❌ gitignored |
| `checkpoint/alapon/59.pth` | **the Alapon model, 47 MB** (+ `train_config.json`, which must sit beside it) | ❌ gitignored |
| `model/checkpoints/audio_visual_encoder.pth` | audio encoder, 11 MB — required | ❌ gitignored |
| `dataset/redwan/` | **not stored here** — see below | ❌ |

Every gitignored file above is already on this machine — the copy from `Fydp_v2` brought
them across. They are excluded from *version control*, not missing. A teammate cloning
fresh gets the code and no weights, which is correct: they cannot run this without a GPU
anyway, and the app runs fine without an avatar.

Weights are gitignored deliberately: GitHub warns above 50 MB, and a 1.3 GB repo
punishes every teammate who clones it. They live on disk, not in history.

---

## The dataset is not in git

The reference frames (`full_body_img/`, 7,717 JPGs) are **1.27 GB**, so they are
never committed. The service looks for them at `./dataset/redwan` (gitignored) by
default. If your copy lives elsewhere - for example in the `Fydp_v2` project -
put its path in your own `avatar-service/.env`:

```
SYNCTALK_DATASET=<path to>/SyncTalk_2D/dataset/redwan
```

The folder **must** contain both `full_body_img/` and `landmarks/` - the server
derives both paths from that one value, so they cannot be split apart.

**Moving to a GPU box?** Copy that whole `redwan` folder across and point
`SYNCTALK_DATASET` at it. Nothing else changes.

## Security

The service has **no login**. It listens on `127.0.0.1` (this machine only) by
default; only set `SYNCTALK_HOST=0.0.0.0` when the backend runs on another
machine on a network you trust. It also closes any session nobody connects to
within 30 s and refuses more than 4 open sessions, so a stray page or a curious
neighbour cannot tie up the GPU.

---

## Running it

```bash
conda activate synctalk
```

```bash
cd avatar-service
```

```bash
cp .env.example .env
```

```bash
./run.ps1
```

`run.ps1` reads `.env`, checks the checkpoint and dataset exist before starting, and
fails with a clear message rather than a stack trace if either is missing.

Equivalent raw command:

```bash
python avatar_server_ws.py --checkpoint checkpoint/alapon/59.pth --dataset <dataset-dir> --mode ave --port 5001 --out_size 720
```

`--mode ave` must match how the checkpoint was trained. Do not change it for Alapon.

Startup takes about two minutes: it scans every landmark, builds the 100-frame idle clip
and warms the GPU so the first reply does not stutter. `/health` reports
`models_loaded: true` once it is serving.

### What the Alapon server does that the first copy did not

- **Idle is real footage.** Redwan's recording ends on a deliberate closed-mouth
  segment; the idle clip is pinned to it (`--idle_range 7639 7716`), clear of the
  recording glitch at 7638→7639 that used to snap the head once per loop.
- **Speech has its own footage** (`--speech_range 1643 1857`), recorded talking, so
  the head moves naturally under the generated mouth.
- **The GPU and CPU overlap**: one frame's forward pass runs while the previous one is
  composited and encoded. Pixel-identical output, ~35 ms/frame instead of ~46 on a
  laptop RTX 3050 — under the 40 ms that 25 fps allows.
- **Edge feathering** on the top and sides of the generated crop removes a bright dot
  beside the nose that the UNet's corner pixels produced.
- Each `Utterance done` log line reports frames rendered vs repeated and ms/render —
  the number to watch for latency.

**Plug the laptop in.** On battery the GPU drops to its power-saving state and renders
at 80–140 ms/frame; the server then repeats frames to keep up with the voice, so the
mouth moves at a few frames per second. Measured 2026-10-05: 44 of 150 frames rendered
at 136 ms, then 58 of 145 at 83 ms, with the GPU at 210 of 2100 MHz.

`alapon_v2` (a retrain on a newer Redwan video) exists in `Fydp_v2` but stopped at
epoch 30 of 60. Do not swap it in until it finishes and is evaluated.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | liveness — the backend polls this to decide online vs offline |
| `GET` | `/idle/info` | idle-loop cache status |
| `GET` | `/idle/frame/{idx}` | single idle frame |
| `POST` | `/session` | returns `{session_id}` |
| `WS` | `/ws/audio/{session_id}` | client sends WAV bytes |
| `WS` | `/ws/video/{session_id}` | server sends `[pts_ms uint64] + jpg bytes` |

The flow: create a session, stream TTS audio in over `/ws/audio`, read timestamped JPEG
frames out of `/ws/video`, and play them against the audio clock in the browser.

---

## Wiring it into LearnQuest

1. Start this service (port 5001).
2. Set `AVATAR_SERVICE_URL=http://localhost:5001` in `backend/.env`, and make sure
   `LLM_PROVIDER=gemini` with a valid key — the voice is Gemini TTS, and the face only
   moves when audio arrives.
3. `GET /api/avatar/status` reports `online: true`. `POST /api/avatar/session` returns
   the two WebSocket URLs plus the idle clip (`idle.frame_url`, `idle.source_map`).
4. The tutor page plays the idle clip back and forth, sends `align` before each reply,
   plays the reply on the audio clock, and resumes idle at `utterance_end.end_source_idx`
   with a short crossfade both ways (`frontend/src/components/avatar/useSyncTalkStream.js`).

Leave `AVATAR_SERVICE_URL` empty and the tutor page shows an "avatar offline" panel; chat
and Teach-Back work normally. That is how Members 2, 3 and 4 should run it.

---

## Notes

- `SYNCTALK_UPSTREAM_README.md` is the original SyncTalk_2D README, kept for the
  training and preprocessing details not repeated here.
- `checkpoint/alapon/` also carries `train_config.json` and `loss_log.csv` — small,
  and useful evidence of the training run for the report.
- Only epoch 59 was copied. The other 12 epoch checkpoints and `last.pth` (656 MB total)
  stayed in `Fydp_v2/SyncTalk_2D/checkpoint/alapon` — pull one over if you ever need to
  compare epochs.
- Upgrading from the old `checkpoint/final_v2/` folder? It is the same file
  (`59.pth`, md5 `3431ee12…`); rename the folder to `alapon`.
