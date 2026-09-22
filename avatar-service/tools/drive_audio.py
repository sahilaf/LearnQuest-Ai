"""Drive the SyncTalk avatar service with a WAV file and check what comes back.

OWNER: Member 1. Companion to frontend/src/components/avatar/useSyncTalkStream.js.

Why this exists
---------------
The service only renders frames when audio arrives. The app drives it with
Gemini TTS through the browser, but that needs the whole stack running; this
drives it from one command so the protocol can be checked on its own.

This pushes a WAV in at one end and validates the framed binary coming out the
other, using exactly the parsing rules the browser hook uses. If this script is
happy, the hook is reading the same bytes the same way.

Usage
-----
    # from the repo root, using the backend venv (needs websockets + httpx only)
    backend/.venv/Scripts/python.exe avatar-service/tools/drive_audio.py \
        --wav "C:/Users/sahil/Dropbox/PC/Documents/projects/Fydp_v2/SyncTalk_2D/dataset/redwan/aud.wav" \
        --seconds 5 --save-frames out/

Deliberately stdlib-only for audio (`wave`), so it runs in the backend venv
without numpy or soundfile - you do not need the conda env to drive the box.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import time
import wave
from pathlib import Path

import httpx
from websockets.asyncio.client import connect

HEADER_BYTES = 16
END_MARKER = 0xFFFFFFFF
FPS = 25


def slice_wav(path: str, chunk_ms: int, max_seconds: float | None):
    """Yield self-contained WAV chunks.

    Each message must be a complete WAV: the server does `sf.read()` per chunk,
    so raw PCM or a split file is rejected as a bad chunk.
    """
    with wave.open(path, "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        frames_per_chunk = int(rate * chunk_ms / 1000)
        budget = int(rate * max_seconds) if max_seconds else source.getnframes()
        sent = 0

        while sent < budget:
            frames = source.readframes(min(frames_per_chunk, budget - sent))
            if not frames:
                break
            sent += len(frames) // (channels * width)

            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as chunk:
                chunk.setnchannels(channels)
                chunk.setsampwidth(width)
                chunk.setframerate(rate)
                chunk.writeframes(frames)
            yield buffer.getvalue()

        print(f"  source: {rate} Hz, {channels}ch, {width * 8}-bit, sent {sent / rate:.2f}s")


async def pump_audio(url: str, chunks: list[bytes], chunk_ms: int) -> None:
    async with connect(url, max_size=None) as socket:
        for chunk in chunks:
            await socket.send(chunk)
            # Feed at roughly real time; blasting the whole file makes the
            # server's catch-up logic fire and the timing report meaningless.
            await asyncio.sleep(chunk_ms / 1000)
        await socket.send(b"__FLUSH__")
        print("  audio: flushed")
        await asyncio.sleep(2.0)


async def drain_video(url: str, save_dir: Path | None, stop: asyncio.Event) -> dict:
    stats = {
        "segments": 0,
        "frames": 0,
        "audio_bytes": 0,
        "control": [],
        "bad_headers": 0,
        "first_frame_at": None,
        "sizes": set(),
    }
    started = time.monotonic()
    expected: dict[int, int] = {}
    saved = 0

    async with connect(url, max_size=None) as socket:
        while not stop.is_set():
            try:
                message = await asyncio.wait_for(socket.recv(), timeout=5.0)
            except asyncio.TimeoutError:
                break

            if isinstance(message, str):
                stats["control"].append(message[:120])
                continue

            if len(message) < HEADER_BYTES:
                stats["bad_headers"] += 1
                continue

            # Same parse as the browser hook: little-endian, 4 x uint32.
            segment = int.from_bytes(message[0:4], "little")
            frame_index = int.from_bytes(message[4:8], "little")
            total_frames = int.from_bytes(message[8:12], "little")
            duration_ms = int.from_bytes(message[12:16], "little")
            body = message[HEADER_BYTES:]

            if frame_index == END_MARKER:
                stats["segments"] += 1
                stats["audio_bytes"] += len(body)
                expected[segment] = total_frames
                # 16-bit mono @ 24 kHz: bytes should match the stated duration.
                implied_ms = len(body) / 2 / 24000 * 1000
                if abs(implied_ms - duration_ms) > 60:
                    print(
                        f"  ! segment {segment}: header says {duration_ms}ms, "
                        f"PCM is {implied_ms:.0f}ms"
                    )
            else:
                stats["frames"] += 1
                if stats["first_frame_at"] is None:
                    stats["first_frame_at"] = time.monotonic() - started
                # JPEG magic - proves it is an image, not a misaligned body.
                if not body.startswith(b"\xff\xd8"):
                    stats["bad_headers"] += 1
                if save_dir and saved < 12:
                    (save_dir / f"seg{segment:03d}_f{frame_index:04d}.jpg").write_bytes(body)
                    saved += 1

    stats["expected_frames"] = sum(expected.values())
    return stats


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="http://localhost:5001")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--chunk-ms", type=int, default=200)
    parser.add_argument("--save-frames", default=None)
    args = parser.parse_args()

    base = args.service.rstrip("/")
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")

    print(f"health:  {base}/health")
    async with httpx.AsyncClient(timeout=10) as client:
        health = (await client.get(f"{base}/health")).json()
        print(f"  models_loaded={health.get('models_loaded')} device={health.get('device')}")
        if not health.get("models_loaded"):
            print("  ! models are not loaded; frames will not render")

        session = (await client.post(f"{base}/session")).json()
    sid = session["session_id"]
    print(f"session: {sid}")

    print(f"slicing {args.wav} into {args.chunk_ms}ms WAV chunks")
    chunks = list(slice_wav(args.wav, args.chunk_ms, args.seconds))
    print(f"  {len(chunks)} chunks")

    save_dir = None
    if args.save_frames:
        save_dir = Path(args.save_frames)
        save_dir.mkdir(parents=True, exist_ok=True)

    stop = asyncio.Event()
    # Video socket first: frames sent before it connects are lost.
    video_task = asyncio.create_task(drain_video(f"{ws_base}/ws/video/{sid}", save_dir, stop))
    await asyncio.sleep(0.5)
    await pump_audio(f"{ws_base}/ws/audio/{sid}", chunks, args.chunk_ms)
    stop.set()
    stats = await video_task

    print("\n--- results ---")
    print(f"  segments (audio packets): {stats['segments']}")
    print(f"  frames received:          {stats['frames']}")
    print(f"  frames promised:          {stats['expected_frames']}")
    print(f"  audio returned:           {stats['audio_bytes'] / 2 / 24000:.2f}s @ 24 kHz")
    print(f"  implied video length:     {stats['frames'] / FPS:.2f}s @ {FPS} fps")
    if stats["first_frame_at"] is not None:
        print(f"  first frame after:        {stats['first_frame_at']:.2f}s")
    print(f"  malformed bodies:         {stats['bad_headers']}")
    for line in stats["control"]:
        print(f"  control: {line}")
    if save_dir:
        print(f"  sample frames written to: {save_dir.resolve()}")

    ok = stats["frames"] > 0 and stats["segments"] > 0 and stats["bad_headers"] == 0
    # Audio and video must describe the same span; that equality is the whole
    # basis of the browser's lipsync scheduling.
    audio_seconds = stats["audio_bytes"] / 2 / 24000
    drift = abs(audio_seconds - stats["frames"] / FPS)
    if ok and drift > 0.5:
        print(f"  ! audio/video lengths differ by {drift:.2f}s")
        ok = False

    print("\nPASS - the stream matches the protocol the browser hook expects."
          if ok else "\nFAIL - see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
