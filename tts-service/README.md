# tts-service — Redwan's free local voice (Kokoro)

Kokoro-82M (Apache-2.0) via ONNX Runtime, on the CPU — no PyTorch, no GPU, no
API key, no daily quota. It outputs 24 kHz mono PCM, the rate the SyncTalk
avatar consumes, so its audio goes to the face unchanged.

The backend tries this first and falls back to Gemini TTS when it is not
running (`backend/app/services/tts.py`). `.\dev.ps1` starts it automatically
once it is set up.

## Setup (once, ~350 MB)

```powershell
cd tts-service
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
mkdir models
curl.exe -L -o models\kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx
curl.exe -L -o models\voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin
```

Then add to `backend/.env`:

```
LOCAL_TTS_URL=http://127.0.0.1:5002
```

## Run by hand

```powershell
.venv\Scripts\python server.py      # http://127.0.0.1:5002/health
```

## Settings (backend/.env)

| Setting | Default | |
|---|---|---|
| `LOCAL_TTS_URL` | empty (off) | Where this service listens |
| `LOCAL_TTS_VOICE` | `am_michael` | Male voices: `am_adam`, `am_fenrir`, `am_puck`, `bm_george` (British); full list at `/health` |
| `TTS_PREFER` | local first | `gemini` puts Gemini TTS first and this second |

Changing the voice changes the cache key, so lessons are re-read in the new voice.
