/**
 * SyncTalkStage - OWNER: Member 1. See plan.md §6.6.
 *
 * The tutor's face, framed as an instrument panel: a title strip with a live
 * state readout, then the video. `useSyncTalkStream` owns the wire protocol and
 * the audio clock; this component owns the speaking loop and the frame.
 *
 * How speech works
 * ----------------
 * The service is audio-driven - it renders frames only in response to audio it
 * receives, so "speaking" and "animating" are the same act. When `spokenText`
 * changes we synthesize it (`POST /api/avatar/speech` -> raw 24 kHz PCM), push
 * it to the service, and frames come back over the video socket.
 *
 * A reply is spoken in two pieces: its first sentence, then the rest, both
 * requested at once. Gemini TTS costs ~4.5s before any audio plus ~15-25ms per
 * character, so a typical 500-character reply took 9-30s as one request - the
 * student had read the answer before the face said a word. Split, the first
 * sentence is speaking in ~5s and the rest is ready about when it ends. The
 * service's walk carries on across the seam, so it does not show.
 *
 * Two pieces, not one per sentence: the free tier allows 10 TTS requests a
 * day per model, and every piece is a request.
 *
 * It is deliberately incapable of showing a broken state: the moment the stream
 * reports itself unavailable it tells its parent, which swaps to the offline
 * panel. A student should never see a dead black square where a tutor was.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Volume2, VolumeX } from 'lucide-react';

import useSyncTalkStream, { STREAM_STATUS } from './useSyncTalkStream';
import { avatarSession, synthesizeSpeech } from '../../api/avatar';

/** First piece: one sentence, so speech starts as soon as possible. */
const FIRST_PIECE_MAX_CHARS = 160;
/** The rest goes in one request, under the backend's 1200-character cap. */
const PIECE_MAX_CHARS = 1100;
/** Both pieces of a normal reply are requested together. */
const SYNTH_CONCURRENCY = 2;

/**
 * Split text into speakable pieces on sentence boundaries. The first piece is
 * kept short; a single over-long sentence is split on its last comma or space.
 */
export function splitForSpeech(text) {
  // A sentence ends at . ! or ? followed by a space, so "3.14" and "e.g.x" stay whole.
  const sentences = text.replace(/\s+/g, ' ').trim().split(/(?<=[.!?]["')\]]*) /)
    .map((sentence) => `${sentence} `);
  const pieces = [];
  let current = '';

  const push = (piece) => {
    const trimmed = piece.trim();
    if (trimmed) pieces.push(trimmed);
  };

  sentences.forEach((sentence) => {
    const limit = pieces.length === 0 ? FIRST_PIECE_MAX_CHARS : PIECE_MAX_CHARS;
    if (current && (current + sentence).length > limit) {
      push(current);
      current = '';
    }
    current += sentence;
    // One sentence too long for a piece: cut on its last comma, else a space.
    for (;;) {
      const max = pieces.length === 0 ? FIRST_PIECE_MAX_CHARS : PIECE_MAX_CHARS;
      if (current.length <= max) break;
      const comma = current.lastIndexOf(', ', max);
      const cut = comma > max / 2 ? comma + 1 : current.lastIndexOf(' ', max);
      const at = cut > 0 ? cut + 1 : max;
      push(current.slice(0, at));
      current = current.slice(at);
    }
    // The first piece is one sentence on purpose: it decides time-to-voice.
    if (pieces.length === 0 && current.trim().length >= 40) {
      push(current);
      current = '';
    }
  });
  push(current);
  return pieces;
}

export default function SyncTalkStage({
  spokenText = '',
  onSpeechEnd = null,
  muted = false,
  onToggleMute = null,
  onUnavailable = null,
  onStatusChange = null,
  fps = 25,
  sampleRate = 24000,
  // Filled with {streamAudio, endStream, stopNow, isAudible} so the page can
  // stream the live tutor's voice into the face.
  controllerRef = null,
  onDisconnect = null,
  // Laid over the bottom of the video, e.g. the live call's turn indicator.
  overlay = null,
}) {
  // Identity-stable so the hook does not tear the socket down on every render.
  const createSession = useCallback(() => avatarSession(), []);
  const [synthesizing, setSynthesizing] = useState(false);

  const {
    canvasRef, status, error, speaking, speak, interrupt, resume,
    streamAudio, endStream, stopNow, isAudible,
  } = useSyncTalkStream({
    enabled: true,
    muted,
    fps,
    sampleRate,
    createSession,
  });

  const synthesizingRef = useRef(false);
  synthesizingRef.current = synthesizing;
  useEffect(() => {
    if (!controllerRef) return undefined;
    controllerRef.current = status === STREAM_STATUS.LIVE ? {
      streamAudio,
      endStream,
      stopNow,
      resume,
      isAudible: () => synthesizingRef.current || isAudible(),
    } : null;
    return () => { controllerRef.current = null; };
  }, [controllerRef, status, streamAudio, endStream, stopNow, resume, isAudible]);

  // Held in a ref so a parent re-render cannot restart an utterance mid-sentence.
  const onSpeechEndRef = useRef(onSpeechEnd);
  useEffect(() => {
    onSpeechEndRef.current = onSpeechEnd;
  }, [onSpeechEnd]);

  useEffect(() => {
    onStatusChange?.(status);
    if (status === STREAM_STATUS.UNAVAILABLE) onUnavailable?.(error);
  }, [status, error, onStatusChange, onUnavailable]);

  useEffect(() => {
    if (!spokenText || status !== STREAM_STATUS.LIVE) return undefined;

    let cancelled = false;
    let finished = false;
    // Whatever she was saying is now stale - drop it before the new line.
    interrupt();
    resume();
    setSynthesizing(true);

    const pieces = splitForSpeech(spokenText);
    // Started in order, at most SYNTH_CONCURRENCY ahead of the piece being
    // spoken. A piece that fails resolves to null and is skipped.
    const pending = [];
    let started = 0;
    let spokenCount = 0;
    const startNext = () => {
      while (!cancelled && started < pieces.length && started - spokenCount < SYNTH_CONCURRENCY) {
        pending.push(synthesizeSpeech(pieces[started]).catch(() => null));
        started += 1;
      }
    };

    (async () => {
      try {
        startNext();
        for (let i = 0; i < pieces.length && !cancelled; i += 1) {
          const pcm = await pending[i];
          spokenCount = i + 1;
          startNext();
          if (cancelled) return;
          setSynthesizing(false);
          // A 503 is "no voice configured", which the offline panel explains.
          // Anything else is transient: skip the piece, keep talking.
          if (pcm) await speak(pcm, sampleRate);
        }
      } finally {
        finished = true;
        if (!cancelled) {
          setSynthesizing(false);
          onSpeechEndRef.current?.();
        }
      }
    })();

    return () => {
      cancelled = true;
      setSynthesizing(false);
      // Taken away mid-reply - the student asked something new. Stop talking
      // now rather than finishing an answer to the old question. Not after a
      // normal finish: the service may still be rendering the last words.
      if (!finished) interrupt();
    };
  }, [spokenText, status, speak, interrupt, resume, sampleRate]);

  const connecting = status === STREAM_STATUS.CONNECTING;
  const active = speaking || synthesizing;
  let label = 'Listening';
  if (speaking) label = 'Speaking';
  else if (synthesizing) label = 'Thinking';

  return (
    <div className="panel w-full">
      <div className="panel-head">
        <span className="label">Tutor</span>
        <span className="flex items-center gap-3 text-2xs font-medium text-muted">
          {/* During a live call the overlay is the one source of truth; two
              status readouts that disagree for half a second is worse than one. */}
          {!overlay && (
            <span className="flex items-center gap-2">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  active ? 'animate-pulse bg-easy' : 'bg-line-strong'
                }`}
              />
              {connecting ? 'Connecting' : label}
            </span>
          )}
          {onDisconnect && (
            <button
              type="button"
              onClick={onDisconnect}
              className="rounded border border-line px-2 py-0.5 text-2xs text-muted transition-colors hover:border-muted hover:text-ink"
            >
              Disconnect
            </button>
          )}
        </span>
      </div>

      <div
        className="relative aspect-square w-full bg-canvas"
        // Browsers hold an AudioContext suspended until a user gesture; without
        // this the very first utterance can arrive with the clock still paused.
        onClick={resume}
        onKeyDown={resume}
        role="presentation"
      >
        <canvas ref={canvasRef} className="h-full w-full object-cover" />

        {overlay && !connecting && (
          <div className="pointer-events-none absolute inset-x-3 bottom-3 flex justify-start">{overlay}</div>
        )}

        {connecting && (
          <div className="absolute inset-0 flex items-center justify-center bg-canvas">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-line-strong border-t-primary-400" />
          </div>
        )}

        {onToggleMute && (
          <button
            type="button"
            onClick={onToggleMute}
            title={muted ? 'Unmute voice' : 'Mute voice'}
            className="absolute bottom-3 right-3 flex h-10 w-10 items-center justify-center rounded border border-line-strong bg-surface/90 text-body backdrop-blur transition-colors hover:border-muted hover:text-ink"
          >
            {muted ? <VolumeX className="h-4.5 w-4.5" /> : <Volume2 className="h-4.5 w-4.5" />}
          </button>
        )}
      </div>
    </div>
  );
}
