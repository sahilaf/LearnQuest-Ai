/**
 * AvatarStage - OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
 * See plan.md §6.6, §6.7.
 *
 * The single entry point for the tutor's face: SyncTalk running Alapon,
 * streaming real video of a trained face over a WebSocket.
 *
 * Opt-in. Nothing connects when the page opens: the student presses Connect,
 * and only then is the service asked whether it is up and a GPU session
 * opened. A page that grabbed a GPU session (and started an idle video) for
 * every visitor was both wasteful and the opposite of calm.
 *
 * Once connected the avatar either runs or says why it cannot; it never
 * quietly substitutes something else.
 */
import { useCallback, useEffect, useState } from 'react';
import { Sparkles, Video } from 'lucide-react';

import AvatarOffline, { AvatarPreview } from './AvatarOffline';
import SyncTalkStage from './SyncTalkStage';
import { STREAM_STATUS } from './useSyncTalkStream';
import { avatarStatus } from '../../api/avatar';

/** What the student sees before connecting: a still and one clear action. */
function AvatarConnect({ onConnect }) {
  return (
    <div className="panel w-full">
      <div className="panel-head">
        <span className="label">Tutor</span>
        <span className="flex items-center gap-2 text-2xs font-medium text-faint">
          <span className="h-1.5 w-1.5 rounded-full bg-line-strong" />
          Not connected
        </span>
      </div>
      {/* Compact on phones, so the tab's own action stays above the fold. */}
      <div className="relative flex w-full flex-col items-center justify-center bg-canvas p-6 text-center lg:aspect-square">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_38%,rgb(var(--primary-600)/0.16),transparent_62%)]" />
        <div className="relative flex flex-col items-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-pill border border-primary-500/40 bg-primary-500/10 text-primary-300">
            <Sparkles className="h-6 w-6" />
          </span>
          <p className="mt-4 text-lg font-semibold text-ink">See your tutor</p>
          <p className="mt-1 max-w-[16rem] text-sm text-muted">
            Connect to a real face that speaks every answer. Optional - voice
            and text work without it.
          </p>
          {onConnect && (
            <button
              type="button"
              onClick={onConnect}
              className="mt-5 inline-flex items-center gap-2 rounded bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500"
            >
              <Video className="h-4 w-4" />
              Connect avatar
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AvatarStage({
  spokenText = '',
  isSpeaking = false,
  onSpeechEnd = null,
  audioMuted = false,
  onToggleMute = null,
  // Marketing surfaces want the tutor as an image, not a live session.
  preview = false,
  // Opt-in connection, owned by the page so other panels know whether the
  // face is there to speak through.
  connected = false,
  onConnect = null,
  onDisconnect = null,
  onAvailabilityChange = null,
  controllerRef = null,
  overlay = null,
}) {
  const [availability, setAvailability] = useState(null);
  const [streamFailed, setStreamFailed] = useState(false);

  useEffect(() => {
    if (preview || !connected) {
      setAvailability(null);
      setStreamFailed(false);
      return undefined;
    }
    let cancelled = false;

    avatarStatus()
      .then((data) => {
        if (!cancelled) setAvailability(data);
      })
      .catch(() => {
        if (!cancelled) {
          setAvailability({ online: false, reason: 'Could not reach the backend.' });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [preview, connected]);

  // Latched: once a stream has failed we stay offline until the student
  // disconnects and tries again, rather than hammering a box that is down.
  const handleUnavailable = useCallback(() => setStreamFailed(true), []);
  const handleStatusChange = useCallback((status) => {
    if (status === STREAM_STATUS.LIVE) setStreamFailed(false);
  }, []);

  const live = Boolean(connected && availability?.online && !streamFailed);
  useEffect(() => {
    onAvailabilityChange?.(live);
  }, [live, onAvailabilityChange]);

  if (preview) return <AvatarPreview />;

  if (!connected) return <AvatarConnect onConnect={onConnect} />;

  if (availability === null) {
    return (
      <div className="flex aspect-square w-full items-center justify-center rounded-lg border border-line bg-surface">
        <span className="h-6 w-6 animate-spin rounded-full border-2 border-line-strong border-t-primary-400" />
      </div>
    );
  }

  if (!availability.online || streamFailed) {
    return (
      <AvatarOffline
        reason={streamFailed ? 'Avatar service is not reachable' : availability.reason}
        onBack={onDisconnect}
      />
    );
  }

  return (
    <SyncTalkStage
      // Only hand over text the caller is actually asking to be spoken;
      // otherwise a re-render would replay the last line.
      spokenText={isSpeaking ? spokenText : ''}
      onSpeechEnd={onSpeechEnd}
      muted={audioMuted}
      onToggleMute={onToggleMute}
      onUnavailable={handleUnavailable}
      onStatusChange={handleStatusChange}
      fps={availability.fps || 25}
      sampleRate={availability.sample_rate || 24000}
      controllerRef={controllerRef}
      onDisconnect={onDisconnect}
      overlay={overlay}
    />
  );
}
