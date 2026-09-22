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
 * It is deliberately incapable of showing a broken state: the moment the stream
 * reports itself unavailable it tells its parent, which swaps to the offline
 * panel. A student should never see a dead black square where a tutor was.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Volume2, VolumeX } from 'lucide-react';

import useSyncTalkStream, { STREAM_STATUS } from './useSyncTalkStream';
import { avatarSession, synthesizeSpeech } from '../../api/avatar';

export default function SyncTalkStage({
  spokenText = '',
  onSpeechEnd = null,
  muted = false,
  onToggleMute = null,
  onUnavailable = null,
  onStatusChange = null,
  fps = 25,
  sampleRate = 24000,
}) {
  // Identity-stable so the hook does not tear the socket down on every render.
  const createSession = useCallback(() => avatarSession(), []);
  const [synthesizing, setSynthesizing] = useState(false);

  const { canvasRef, status, error, speaking, speak, interrupt, resume } = useSyncTalkStream({
    enabled: true,
    muted,
    fps,
    sampleRate,
    createSession,
  });

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
    // Whatever she was saying is now stale - drop it before the new line.
    interrupt();
    resume();
    setSynthesizing(true);

    synthesizeSpeech(spokenText)
      .then((pcm) => {
        if (cancelled) return null;
        setSynthesizing(false);
        return speak(pcm, sampleRate);
      })
      .catch(() => {
        // A 503 is "no voice configured", which the offline panel explains.
        // Anything else is transient. Either way the turn must not hang.
        if (!cancelled) setSynthesizing(false);
      })
      .finally(() => {
        if (!cancelled) onSpeechEndRef.current?.();
      });

    return () => {
      cancelled = true;
      setSynthesizing(false);
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
        <span className="flex items-center gap-2 text-2xs font-medium text-muted">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              active ? 'animate-pulse bg-easy' : 'bg-line-strong'
            }`}
          />
          {label}
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
