/**
 * useSyncTalkStream - OWNER: Member 1. See plan.md §6.6.
 *
 * WebSocket client for the SyncTalk avatar service. Replaces the old
 * `<img src={videoStreamUrl}>`, which assumed MJPEG over HTTP; the service
 * actually sends framed binary over a WebSocket and never served that URL.
 *
 * Wire format (avatar-service/avatar_server_ws.py)
 * ------------------------------------------------
 * Every binary message is a 16-byte little-endian header plus a body:
 *
 *   [4B segment_id][4B frame_index][4B total_frames][4B audio_duration_ms]
 *
 *   frame_index === 0xFFFFFFFF  ->  body is signed 16-bit mono PCM @ 24 kHz
 *                                   for the whole segment, sent BEFORE its
 *                                   frames so audio can start immediately
 *   otherwise                   ->  body is one JPEG frame of that segment
 *
 * Text messages are control JSON: {"type": "utterance_end"} and
 * {"type": "reset_done"}.
 *
 * Audio is the master clock
 * -------------------------
 * The server renders frames as fast as the GPU allows, which is not real time,
 * so frames cannot drive playback - the mouth would drift from the voice. Each
 * segment's audio is scheduled on the AudioContext clock at a known time, and
 * the render loop then picks whichever frame belongs at `ctx.currentTime`. Late
 * frames are skipped rather than queued, and a missing frame repeats the last
 * one, so the voice never stalls waiting for a picture.
 *
 * This is also why muting only zeroes the gain node: the buffers still play, so
 * the clock keeps running and the face stays in sync when sound comes back.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const HEADER_BYTES = 16;
const END_MARKER = 0xffffffff;

/** Matches CLIENT_GATE_S in the service: how far ahead audio is scheduled. */
const PREBUFFER_SECONDS = 0.3;

/** Segments finished more than this long ago are released. */
const SEGMENT_TTL_SECONDS = 1.0;

/** Give up on a silent socket rather than showing a dead canvas forever. */
const CONNECT_TIMEOUT_MS = 8000;

/**
 * Audio is pushed in slices this long. The service accumulates 200ms before
 * running a feature batch, so smaller slices buy nothing and larger ones delay
 * the first frame.
 */
const SEND_CHUNK_MS = 200;

/**
 * Wrap raw PCM in a WAV container.
 *
 * Required, not cosmetic: the service calls `soundfile.read()` on every message
 * it receives, so a message must be a complete, self-describing file. Raw PCM
 * is logged as a bad chunk and dropped silently.
 */
function pcmToWav(pcmBytes, sampleRate) {
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  const writeAscii = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };

  writeAscii(0, 'RIFF');
  view.setUint32(4, 36 + pcmBytes.byteLength, true);
  writeAscii(8, 'WAVE');
  writeAscii(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // format: PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate: 16-bit mono
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeAscii(36, 'data');
  view.setUint32(40, pcmBytes.byteLength, true);

  const wav = new Uint8Array(44 + pcmBytes.byteLength);
  wav.set(new Uint8Array(header), 0);
  wav.set(new Uint8Array(pcmBytes), 44);
  return wav;
}

export const STREAM_STATUS = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LIVE: 'live',
  UNAVAILABLE: 'unavailable',
};

/**
 * @param {object}  options
 * @param {boolean} options.enabled  open the stream (false tears it down)
 * @param {boolean} options.muted    silence audio without breaking sync
 * @param {number}  options.fps      frames per second the service emits
 * @param {number}  options.sampleRate  PCM sample rate of the returned audio
 * @param {function} options.createSession  async () => {video_ws_url, audio_ws_url, ...}
 */
export default function useSyncTalkStream({
  enabled = false,
  muted = false,
  fps = 25,
  sampleRate = 24000,
  createSession,
}) {
  const canvasRef = useRef(null);
  const [status, setStatus] = useState(STREAM_STATUS.IDLE);
  const [error, setError] = useState(null);
  const [speaking, setSpeaking] = useState(false);

  const audioCtxRef = useRef(null);
  const gainRef = useRef(null);
  const videoSocketRef = useRef(null);
  const audioSocketRef = useRef(null);
  const segmentsRef = useRef(new Map());
  const nextStartRef = useRef(0);
  const lastBitmapRef = useRef(null);
  const rafRef = useRef(null);
  // Bumped on every new utterance so an in-flight send can tell it is stale.
  const utteranceRef = useRef(0);

  // Read inside the render loop, so changing them must not restart the stream.
  const fpsRef = useRef(fps);
  const sampleRateRef = useRef(sampleRate);
  useEffect(() => {
    fpsRef.current = fps;
    sampleRateRef.current = sampleRate;
  }, [fps, sampleRate]);

  // Mute is a gain change, never a teardown - see the header comment.
  useEffect(() => {
    if (gainRef.current) gainRef.current.gain.value = muted ? 0 : 1;
  }, [muted]);

  const releaseSegment = useCallback((id) => {
    const segment = segmentsRef.current.get(id);
    if (!segment) return;
    segment.frames.forEach((bitmap) => {
      if (bitmap && bitmap !== lastBitmapRef.current) bitmap.close?.();
    });
    segmentsRef.current.delete(id);
  }, []);

  const drawBitmap = useCallback((bitmap) => {
    const canvas = canvasRef.current;
    if (!canvas || !bitmap) return;
    if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
    }
    const ctx2d = canvas.getContext('2d');
    if (ctx2d) ctx2d.drawImage(bitmap, 0, 0);
  }, []);

  /** Pick the frame that belongs at the current audio time and draw it. */
  const renderLoop = useCallback(() => {
    const audioCtx = audioCtxRef.current;
    if (!audioCtx) return;

    const now = audioCtx.currentTime;
    const framesPerSecond = fpsRef.current;
    let active = null;

    segmentsRef.current.forEach((segment, id) => {
      const endsAt = segment.startAt + segment.totalFrames / framesPerSecond;
      if (now >= segment.startAt && now < endsAt) {
        active = segment;
      } else if (endsAt + SEGMENT_TTL_SECONDS < now) {
        releaseSegment(id);
      }
    });

    if (active) {
      const index = Math.min(
        active.totalFrames - 1,
        Math.max(0, Math.floor((now - active.startAt) * framesPerSecond)),
      );
      // Fall back to the last drawn frame when this one has not arrived yet:
      // a repeated frame reads as a held expression, a blank canvas reads as
      // a crash.
      const bitmap = active.frames[index] || lastBitmapRef.current;
      if (bitmap && bitmap !== lastBitmapRef.current) lastBitmapRef.current = bitmap;
      if (bitmap) drawBitmap(bitmap);
      setSpeaking(true);
    } else {
      setSpeaking(false);
    }

    rafRef.current = requestAnimationFrame(renderLoop);
  }, [drawBitmap, releaseSegment]);

  const handleAudioPacket = useCallback((segmentId, totalFrames, body) => {
    const audioCtx = audioCtxRef.current;
    if (!audioCtx) return;

    // The body may not be 2-byte aligned inside the larger buffer, so copy
    // rather than viewing it in place - Int16Array would throw otherwise.
    const pcm = new Int16Array(body.slice(0));
    const samples = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i += 1) samples[i] = pcm[i] / 32768;

    const buffer = audioCtx.createBuffer(1, samples.length || 1, sampleRateRef.current);
    buffer.copyToChannel(samples, 0);

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(gainRef.current);

    // Never schedule in the past: a late segment would play instantly and the
    // frames would already be stale.
    const startAt = Math.max(audioCtx.currentTime + PREBUFFER_SECONDS, nextStartRef.current);
    source.start(startAt);
    nextStartRef.current = startAt + buffer.duration;

    segmentsRef.current.set(segmentId, {
      startAt,
      totalFrames: Math.max(1, totalFrames),
      frames: new Array(Math.max(1, totalFrames)),
    });
  }, []);

  const handleFramePacket = useCallback((segmentId, frameIndex, body) => {
    const segment = segmentsRef.current.get(segmentId);
    // Frames always follow their audio packet. One that does not belongs to a
    // segment we already released, so it is safe to drop.
    if (!segment || frameIndex >= segment.frames.length) return;

    createImageBitmap(new Blob([body], { type: 'image/jpeg' }))
      .then((bitmap) => {
        const current = segmentsRef.current.get(segmentId);
        if (!current) {
          bitmap.close?.();
          return;
        }
        current.frames[frameIndex] = bitmap;
      })
      .catch(() => {
        /* A corrupt frame is not worth failing the stream over. */
      });
  }, []);

  const handleBinary = useCallback(
    (buffer) => {
      if (buffer.byteLength < HEADER_BYTES) return;
      const header = new DataView(buffer, 0, HEADER_BYTES);
      const segmentId = header.getUint32(0, true);
      const frameIndex = header.getUint32(4, true);
      const totalFrames = header.getUint32(8, true);
      const body = buffer.slice(HEADER_BYTES);

      if (frameIndex === END_MARKER) {
        handleAudioPacket(segmentId, totalFrames, body);
      } else {
        handleFramePacket(segmentId, frameIndex, body);
      }
    },
    [handleAudioPacket, handleFramePacket],
  );

  const teardown = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;

    [videoSocketRef, audioSocketRef].forEach((ref) => {
      const socket = ref.current;
      ref.current = null;
      if (socket && socket.readyState <= WebSocket.OPEN) {
        socket.onclose = null;
        socket.onerror = null;
        socket.close();
      }
    });

    Array.from(segmentsRef.current.keys()).forEach(releaseSegment);
    segmentsRef.current.clear();
    lastBitmapRef.current?.close?.();
    lastBitmapRef.current = null;
    nextStartRef.current = 0;

    audioCtxRef.current?.close?.().catch(() => {});
    audioCtxRef.current = null;
    gainRef.current = null;
    setSpeaking(false);
  }, [releaseSegment]);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') {
      teardown();
      setStatus(STREAM_STATUS.IDLE);
      return undefined;
    }

    let cancelled = false;
    let timeoutId = null;

    const fail = (message) => {
      if (cancelled) return;
      setError(message);
      setStatus(STREAM_STATUS.UNAVAILABLE);
      teardown();
    };

    (async () => {
      setStatus(STREAM_STATUS.CONNECTING);
      setError(null);

      let session;
      try {
        session = await createSession();
      } catch {
        // A 503 here is the normal "no GPU box configured" case, not a bug.
        fail('Avatar service is unavailable.');
        return;
      }
      if (cancelled || !session?.video_ws_url) {
        fail('Avatar service returned no stream URL.');
        return;
      }

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) {
        fail('This browser cannot play the avatar audio stream.');
        return;
      }
      const audioCtx = new AudioCtx({ sampleRate: session.sample_rate || sampleRate });
      const gain = audioCtx.createGain();
      gain.gain.value = muted ? 0 : 1;
      gain.connect(audioCtx.destination);
      audioCtxRef.current = audioCtx;
      gainRef.current = gain;

      const socket = new WebSocket(session.video_ws_url);
      socket.binaryType = 'arraybuffer';
      videoSocketRef.current = socket;

      timeoutId = setTimeout(() => {
        if (socket.readyState !== WebSocket.OPEN) fail('Avatar stream did not connect.');
      }, CONNECT_TIMEOUT_MS);

      socket.onopen = () => {
        if (cancelled) return;
        clearTimeout(timeoutId);
        setStatus(STREAM_STATUS.LIVE);
        rafRef.current = requestAnimationFrame(renderLoop);
      };

      socket.onmessage = (event) => {
        if (cancelled) return;
        if (typeof event.data === 'string') return; // control JSON; nothing to do yet
        handleBinary(event.data);
      };

      socket.onerror = () => fail('Avatar stream errored.');
      socket.onclose = () => {
        if (!cancelled) fail('Avatar stream closed.');
      };

      // The audio socket is what makes the face move: the service renders only
      // in response to audio. Its absence never blocks rendering, but nothing
      // will be drawn until something is spoken.
      if (session.audio_ws_url) {
        try {
          const audioSocket = new WebSocket(session.audio_ws_url);
          audioSocket.binaryType = 'arraybuffer';
          audioSocketRef.current = audioSocket;
        } catch {
          audioSocketRef.current = null;
        }
      }
    })();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
      teardown();
    };
    // `muted` is applied by its own effect; including it here would reconnect
    // the socket every time the student toggles sound.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, createSession, handleBinary, renderLoop, teardown, sampleRate]);

  /**
   * Speak raw PCM through the avatar.
   *
   * Sent as a sequence of small WAV files rather than one large one so the
   * service can start rendering while the rest is still arriving - the first
   * frame lands in a few hundred ms instead of after the whole utterance.
   * Paced at roughly real time: firing everything at once makes the server's
   * catch-up logic drop frames it has not rendered yet.
   */
  const speak = useCallback(async (pcmBuffer, pcmSampleRate) => {
    const socket = audioSocketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    if (!pcmBuffer || pcmBuffer.byteLength === 0) return false;

    const rate = pcmSampleRate || sampleRateRef.current;
    const bytesPerChunk = Math.max(2, Math.floor((rate * 2 * SEND_CHUNK_MS) / 1000));
    const utterance = (utteranceRef.current += 1);

    for (let offset = 0; offset < pcmBuffer.byteLength; offset += bytesPerChunk) {
      // A newer utterance started, or the socket went away mid-send: stop
      // rather than interleaving two voices.
      if (utterance !== utteranceRef.current) return false;
      if (audioSocketRef.current?.readyState !== WebSocket.OPEN) return false;

      const slice = pcmBuffer.slice(offset, Math.min(offset + bytesPerChunk, pcmBuffer.byteLength));
      audioSocketRef.current.send(pcmToWav(slice, rate));
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => { setTimeout(resolve, SEND_CHUNK_MS); });
    }

    if (utterance !== utteranceRef.current) return false;
    if (audioSocketRef.current?.readyState !== WebSocket.OPEN) return false;
    audioSocketRef.current.send(new TextEncoder().encode('__FLUSH__'));
    return true;
  }, []);

  /** Abandon the current utterance and clear the service's queue. */
  const interrupt = useCallback(() => {
    utteranceRef.current += 1;
    const socket = audioSocketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'reset' }));
    }
  }, []);

  /** Browsers start an AudioContext suspended until a user gesture. */
  const resume = useCallback(() => {
    audioCtxRef.current?.resume?.().catch(() => {});
  }, []);

  return { canvasRef, status, error, speaking, speak, interrupt, resume };
}
