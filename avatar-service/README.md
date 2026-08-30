# avatar-service — SyncTalk 2D avatar (Tier B)

**Owner:** Member 1 (Lead). See [plan.md](../plan.md) §6.6.

The real-time talking-head service. Brought over from the `Fydp_v2` project, using the
**`redwan`** dataset and the **`final_v2`** checkpoint (epoch 59).

This runs as a **separate process from the LearnQuest backend** — it needs a CUDA GPU
and a conda environment that the FastAPI app does not. The backend talks to it over
HTTP/WebSocket via `AVATAR_SERVICE_URL`.

> **Tier A still ships first.** The browser avatar (Web Speech TTS + viseme lipsync) is
> the fallback and must work on any laptop with no GPU. This service is the upgrade —
> when `AVATAR_SERVICE_URL` is empty, the app degrades to Tier A automatically.

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
| `checkpoint/final_v2/59.pth` | **the trained model, 47 MB** | ❌ gitignored |
| `model/checkpoints/audio_visual_encoder.pth` | audio encoder, 11 MB — required | ❌ gitignored |
| `dataset/redwan/` | **not stored here** — see below | ❌ |

Every gitignored file above is already on this machine — the copy from `Fydp_v2` brought
them across. They are excluded from *version control*, not missing. A teammate cloning
fresh gets the code and no weights, which is correct: they cannot run this without a GPU
anyway, and Tier A is what they should be running.

Weights are gitignored deliberately: GitHub warns above 50 MB, and a 1.3 GB repo
punishes every teammate who clones it. They live on disk, not in history.

---

## The dataset lives outside this repo

The reference frames (`full_body_img/`, 7,717 JPGs) are **1.27 GB**. Copying them into
LearnQuest would mean Dropbox syncing 1.27 GB up and back down for no benefit, so the
service points at the existing copy instead:

```
C:/Users/sahil/Dropbox/PC/Documents/projects/Fydp_v2/SyncTalk_2D/dataset/redwan
```

Set `SYNCTALK_DATASET` in `.env` to change it. The folder **must** contain both
`full_body_img/` and `landmarks/` — the server derives both paths from that one value,
so they cannot be split apart.

**Moving to a GPU box?** Copy that whole `redwan` folder across and repoint
`SYNCTALK_DATASET`. Nothing else changes.

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
python avatar_server_ws.py --checkpoint checkpoint/final_v2/59.pth --dataset <dataset-dir> --mode ave --port 5001
```

`--mode ave` must match how the checkpoint was trained. Do not change it for `final_v2`.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | liveness — the backend polls this to decide Tier A vs Tier B |
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
2. Set `AVATAR_SERVICE_URL=http://localhost:5001` in `backend/.env`.
3. `GET /api/avatar/status` then reports `tier: "B"`, and `POST /api/avatar/speak`
   returns a `video_stream_url` alongside the audio and visemes.
4. The frontend renders Tier B when `video_stream_url` is present, Tier A when it is not.

Leave `AVATAR_SERVICE_URL` empty and the whole app runs Tier A with no GPU — which is
how Members 2, 3 and 4 should run it.

---

## Notes

- `SYNCTALK_UPSTREAM_README.md` is the original SyncTalk_2D README, kept for the
  training and preprocessing details not repeated here.
- `checkpoint/final_v2/` also carries `train_config.json` and `loss_log.csv` — small,
  and useful evidence of the training run for the report.
- Only epoch 59 was copied. The other 12 epoch checkpoints and `last.pth` (656 MB total)
  stayed in `Fydp_v2` — pull one over if you ever need to compare epochs.
