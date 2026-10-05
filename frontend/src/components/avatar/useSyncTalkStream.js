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
 *
 * Idle between replies
 * --------------------
 * The service only renders while audio arrives, so between replies the face
 * plays a pre-rendered idle clip (Alapon's closed-mouth footage) instead of
 * freezing on the last speech frame. The clip plays back and forth, never
 * wrapping - it is one sweep through the recording, so wrapping would snap the
 * head back every loop. Before a reply the client tells the service where idle
 * is ("align") so speech starts from nearby footage; after it, `utterance_end`
 * says where speech stopped and idle resumes at the nearest frame. Both seams
 * crossfade over a few frames. Same scheme as the Fydp_v2 LiveKit agent.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const HEADER_BYTES = 16;
const END_MARKER = 0xffffffff;

/**
 * Matches CLIENT_GATE_S in the service: how far ahead audio is scheduled.
 *
 * 0.6 s, not 0.3: on a laptop GPU a frame takes ~45 ms against a 40 ms budget,
 * so the service runs up to 10 frames (0.4 s) behind before it catches up, and
 * audio arrives in 0.2 s batches. With only 0.3 s of cushion the next batch
 * regularly landed after the previous one had finished playing - a gap in the
 * voice, and the face fell back to idle mid-sentence.
 */
const PREBUFFER_SECONDS = 0.6;

/**
 * Within a reply, a gap shorter than this holds the last frame instead of
 * going idle. Longer means something stalled; idle is then the honest state.
 */
const MAX_HOLD_SECONDS = 4;

/** After the last word, keep the live mic shut this long (room echo). */
const AUDIBLE_TAIL_SECONDS = 0.35;

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
 * The idle clip is encoded at 25 fps but each frame is held this long: half
 * speed reads as calm breathing, full speed as fidgeting. Matches the agent's
 * IDLE_FRAME_HOLD_TICKS = 2 at 25 fps.
 */
const IDLE_FRAME_MS = 80;

/** Frames blended at each idle <-> speech seam (the agent's CROSSFADE_FRAMES). */
const CROSSFADE_FRAMES = 3;

/**
 * Preload the idle clip as plain images.
 *
 * Images, not fetch(): the service sends no CORS headers, and an <img> needs
 * none to be drawn. The canvas is only ever drawn to, never read back, so the
 * cross-origin taint does not matter.
 */
function loadIdleClip(idle) {
  if (!idle?.frame_count || !idle.frame_url) return null;
  const frames = Array.from({ length: idle.frame_count }, (_, index) => {
    const img = new Image();
    img.decoding = 'async';
    img.src = idle.frame_url.replace('{index}', String(index));
    return img;
  });
  return {
    frames,
    sourceMap: idle.source_map?.length ? idle.source_map : frames.map((_, i) => i),
    pos: 0,
    dir: 1,
    stepAt: 0,
  };
}

/** Clip position showing the recording frame nearest `sourceIdx`. */
function idlePosForSource(clip, sourceIdx) {
  let best = 0;
  clip.sourceMap.forEach((source, i) => {
    if (Math.abs(source - sourceIdx) < Math.abs(clip.sourceMap[best] - sourceIdx)) best = i;
  });
  return best;
}

const isDrawable = (src) => Boolean(src) && (!(src instanceof HTMLImageElement)
  || (src.complete && src.naturalWidth > 0));

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
  const idleRef = useRef(null);
  // Recording frame where the last reply ended; idle resumes nearest to it.
  const resumeSourceRef = useRef(null);
  const wasSpeakingRef = useRef(false);
  const crossfadeLeftRef = useRef(0);
  // Scheduled audio, so a barge-in can silence it instead of letting it finish.
  const sourcesRef = useRef(new Set());
  // Live audio streamed in as it arrives (see streamAudio).
  const streamOpenRef = useRef(false);
  const streamBufRef = useRef([]);
  const streamBytesRef = useRef(0);
  const lastSendAtRef = useRef(0);
  // Utterances sent to the service whose utterance_end has not come back yet.
  // While any is open the reply is still coming, whatever the audio clock says.
  const openUtterancesRef = useRef(0);
  const holdSinceRef = useRef(null);
  // Audio scheduled since resetClock(): how much of it has been heard is the
  // clock a lesson narrator highlights words by.
  const clockRef = useRef([]);

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

  /**
   * Draw a speech bitmap or idle image. During a crossfade the new frame is
   * laid over what the canvas already shows at rising opacity, so the seam
   * between idle and speech footage dissolves instead of cutting.
   */
  const drawFrame = useCallback((source) => {
    const canvas = canvasRef.current;
    if (!canvas || !isDrawable(source)) return;
    const width = source.naturalWidth || source.width;
    const height = source.naturalHeight || source.height;
    const resized = canvas.width !== width || canvas.height !== height;
    if (resized) {
      canvas.width = width;
      canvas.height = height;
    }
    const ctx2d = canvas.getContext('2d');
    if (!ctx2d) return;

    let alpha = 1;
    if (crossfadeLeftRef.current > 0 && !resized) {
      alpha = 1 - crossfadeLeftRef.current / (CROSSFADE_FRAMES + 1);
      crossfadeLeftRef.current -= 1;
    }
    ctx2d.globalAlpha = alpha;
    ctx2d.drawImage(source, 0, 0);
    ctx2d.globalAlpha = 1;
  }, []);

  /** Draw the idle clip's current frame and step it, back and forth. */
  const drawIdle = useCallback((nowMs) => {
    const clip = idleRef.current;
    if (!clip) return false;
    const count = clip.frames.length;
    clip.pos = Math.min(Math.max(clip.pos, 0), count - 1);
    const img = clip.frames[clip.pos];
    if (!isDrawable(img)) return false;

    if (nowMs >= clip.stepAt) {
      drawFrame(img);
      clip.stepAt = nowMs + IDLE_FRAME_MS;
      if (count > 1) {
        if (clip.pos + clip.dir < 0 || clip.pos + clip.dir >= count) clip.dir = -clip.dir;
        clip.pos += clip.dir;
      }
    }
    return true;
  }, [drawFrame]);

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
      if (!wasSpeakingRef.current) {
        wasSpeakingRef.current = true;
        crossfadeLeftRef.current = CROSSFADE_FRAMES; // idle -> speech
      }
      const index = Math.min(
        active.totalFrames - 1,
        Math.max(0, Math.floor((now - active.startAt) * framesPerSecond)),
      );
      // Fall back to the last drawn frame when this one has not arrived yet:
      // a repeated frame reads as a held expression, a blank canvas reads as
      // a crash.
      const bitmap = active.frames[index] || lastBitmapRef.current;
      // Only redraw on a new frame, so a crossfade steps once per video frame
      // rather than once per display refresh.
      if (bitmap && bitmap !== lastBitmapRef.current) {
        lastBitmapRef.current = bitmap;
        drawFrame(bitmap);
      }
      holdSinceRef.current = null;
      setSpeaking(true);
    } else if (wasSpeakingRef.current && (openUtterancesRef.current > 0 || now < nextStartRef.current)
      && (holdSinceRef.current === null || now - holdSinceRef.current < MAX_HOLD_SECONDS)) {
      // Mid-reply gap: the next batch is on its way. Hold the last frame - a
      // brief pause reads as a breath, a flash of the idle loop reads as the
      // tutor giving up mid-sentence.
      if (holdSinceRef.current === null) holdSinceRef.current = now;
      setSpeaking(true);
    } else {
      holdSinceRef.current = null;
      const clip = idleRef.current;
      if (wasSpeakingRef.current) {
        wasSpeakingRef.current = false;
        crossfadeLeftRef.current = CROSSFADE_FRAMES; // speech -> idle
        if (clip) {
          if (resumeSourceRef.current !== null) {
            clip.pos = idlePosForSource(clip, resumeSourceRef.current);
            resumeSourceRef.current = null;
          }
          clip.stepAt = 0;
        }
      }
      // No idle clip (cache not built yet): hold the last speech frame.
      drawIdle(performance.now());
      setSpeaking(false);
    }

    rafRef.current = requestAnimationFrame(renderLoop);
  }, [drawFrame, drawIdle, releaseSegment]);

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
    clockRef.current.push({ startAt, duration: buffer.duration });
    sourcesRef.current.add(source);
    source.onended = () => sourcesRef.current.delete(source);

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

  /** Text frames are control JSON from the service. */
  const handleControl = useCallback((text) => {
    let message;
    try {
      message = JSON.parse(text);
    } catch {
      return;
    }
    if (message?.type === 'utterance_end') {
      openUtterancesRef.current = Math.max(0, openUtterancesRef.current - 1);
    }
    if (message?.type === 'utterance_end' && Number.isFinite(message.end_source_idx)) {
      resumeSourceRef.current = message.end_source_idx;
    }
  }, []);

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
    idleRef.current?.frames.forEach((img) => { img.src = ''; });
    idleRef.current = null;
    resumeSourceRef.current = null;
    wasSpeakingRef.current = false;
    crossfadeLeftRef.current = 0;

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

    // Deferred one tick: React StrictMode (every dev run) mounts, unmounts and
    // remounts at once, and starting immediately opened two GPU sessions per
    // "Connect avatar" - the first abandoned. The throwaway mount's timer is
    // cleared before it fires.
    const startTimer = setTimeout(() => (async () => {
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
      idleRef.current = loadIdleClip(session.idle);

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
        if (typeof event.data === 'string') {
          handleControl(event.data);
          return;
        }
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
    })(), 0);

    return () => {
      cancelled = true;
      clearTimeout(startTimer);
      if (timeoutId) clearTimeout(timeoutId);
      teardown();
    };
    // `muted` is applied by its own effect; including it here would reconnect
    // the socket every time the student toggles sound.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, createSession, handleBinary, handleControl, renderLoop, teardown, sampleRate]);

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
    openUtterancesRef.current += 1;
    lastSendAtRef.current = performance.now();

    // Start the service's footage walk where idle is, but only when the face
    // really is idle: mid-reply the walk already continues from the last
    // segment, and re-aligning to a stale idle position would jump the head.
    const clip = idleRef.current;
    if (clip && !wasSpeakingRef.current) {
      socket.send(JSON.stringify({ type: 'align', source_idx: clip.sourceMap[clip.pos] }));
    }

    for (let offset = 0; offset < pcmBuffer.byteLength; offset += bytesPerChunk) {
      // A newer utterance started, or the socket went away mid-send: stop
      // rather than interleaving two voices.
      if (utterance !== utteranceRef.current) return false;
      if (audioSocketRef.current?.readyState !== WebSocket.OPEN) return false;

      const slice = pcmBuffer.slice(offset, Math.min(offset + bytesPerChunk, pcmBuffer.byteLength));
      audioSocketRef.current.send(pcmToWav(slice, rate));
      lastSendAtRef.current = performance.now();
      await new Promise((resolve) => { setTimeout(resolve, SEND_CHUNK_MS); });
    }

    if (utterance !== utteranceRef.current) return false;
    if (audioSocketRef.current?.readyState !== WebSocket.OPEN) return false;
    audioSocketRef.current.send(new TextEncoder().encode('__FLUSH__'));
    return true;
  }, []);

  /**
   * Live audio: forward chunks as they arrive instead of a whole buffer.
   *
   * Gemini Live produces speech about as fast as it plays, so no pacing is
   * needed; chunks are batched to >= 100 ms only to keep the service from
   * decoding a WAV file every few milliseconds. `endStream` closes the
   * utterance so the service renders the tail and reports where it ended.
   */
  const sendStreamBuffer = useCallback((rate) => {
    const socket = audioSocketRef.current;
    if (!streamBytesRef.current || socket?.readyState !== WebSocket.OPEN) return;
    const joined = new Uint8Array(streamBytesRef.current);
    let offset = 0;
    streamBufRef.current.forEach((part) => { joined.set(new Uint8Array(part), offset); offset += part.byteLength; });
    streamBufRef.current = [];
    streamBytesRef.current = 0;
    socket.send(pcmToWav(joined.buffer, rate));
    lastSendAtRef.current = performance.now();
  }, []);

  const streamAudio = useCallback((chunk, rate = sampleRateRef.current) => {
    const socket = audioSocketRef.current;
    if (!chunk?.byteLength || socket?.readyState !== WebSocket.OPEN) return;
    if (!streamOpenRef.current) {
      streamOpenRef.current = true;
      utteranceRef.current += 1;
      openUtterancesRef.current += 1;
      const clip = idleRef.current;
      if (clip && !wasSpeakingRef.current) {
        socket.send(JSON.stringify({ type: 'align', source_idx: clip.sourceMap[clip.pos] }));
      }
    }
    streamBufRef.current.push(chunk);
    streamBytesRef.current += chunk.byteLength;
    if (streamBytesRef.current >= rate * 2 * 0.1) sendStreamBuffer(rate);
  }, [sendStreamBuffer]);

  const endStream = useCallback((rate = sampleRateRef.current) => {
    if (!streamOpenRef.current) return;
    sendStreamBuffer(rate);
    streamOpenRef.current = false;
    if (audioSocketRef.current?.readyState === WebSocket.OPEN) {
      audioSocketRef.current.send(new TextEncoder().encode('__FLUSH__'));
    }
  }, [sendStreamBuffer]);

  /**
   * Whether the face is talking or about to: a reply is still streaming in,
   * the service has not yet confirmed the end of what it was sent, or audio
   * is scheduled. The live call keeps its microphone shut while this is
   * true - a mic that reopens before the last word is heard picks the
   * tutor's own voice off the speakers and cuts the reply short.
   */
  const isAudible = useCallback(() => {
    const ctx = audioCtxRef.current;
    if (streamOpenRef.current) return true;
    // Bounded, so a lost utterance_end cannot keep the mic shut forever.
    if (openUtterancesRef.current > 0 && performance.now() - lastSendAtRef.current < 8000) return true;
    return Boolean(ctx && ctx.currentTime < nextStartRef.current + AUDIBLE_TAIL_SECONDS);
  }, []);

  /** Abandon the current utterance and clear the service's queue. */
  const interrupt = useCallback(() => {
    utteranceRef.current += 1;
    // The reset discards queued audio, so its utterance_end may never come.
    openUtterancesRef.current = 0;
    const socket = audioSocketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'reset' }));
    }
  }, []);

  /**
   * Stop talking now: the service's queue, everything already scheduled, and
   * any live stream in progress. For barge-in and for leaving a call - an
   * ordinary interrupt() lets the last ~0.3 s already scheduled play out.
   */
  const stopNow = useCallback(() => {
    interrupt();
    streamOpenRef.current = false;
    streamBufRef.current = [];
    streamBytesRef.current = 0;
    sourcesRef.current.forEach((src) => { try { src.stop(); } catch { /* ended */ } });
    sourcesRef.current.clear();
    Array.from(segmentsRef.current.keys()).forEach(releaseSegment);
    nextStartRef.current = 0;
  }, [interrupt, releaseSegment]);

  /** Start counting heard audio from zero. */
  const resetClock = useCallback(() => { clockRef.current = []; }, []);

  /** Seconds of audio scheduled since resetClock() that have been played. */
  const heardSeconds = useCallback(() => {
    const now = audioCtxRef.current?.currentTime ?? 0;
    return clockRef.current.reduce(
      (sum, c) => sum + Math.min(c.duration, Math.max(0, now - c.startAt)), 0,
    );
  }, []);

  /** Browsers start an AudioContext suspended until a user gesture. */
  const resume = useCallback(() => {
    audioCtxRef.current?.resume?.().catch(() => {});
  }, []);

  return {
    canvasRef, status, error, speaking, speak, interrupt, resume,
    streamAudio, endStream, stopNow, isAudible, resetClock, heardSeconds,
  };
}
