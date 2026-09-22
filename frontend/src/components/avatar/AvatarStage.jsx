/**
 * AvatarStage - OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
 * See plan.md §6.6, §6.7.
 *
 * The single entry point for the tutor's face. There is one avatar: SyncTalk,
 * streaming real video of a trained face over a WebSocket.
 *
 * The old SVG avatar and its Web Speech voice ("Tier A") were removed on
 * 2026-09-22. They were a stand-in from before the real pipeline existed, and
 * keeping two avatars meant two lipsync implementations, two voices that could
 * both fire at once, and a cartoon that quietly replaced the photoreal tutor
 * whenever anything went wrong - which is exactly when you want to know.
 *
 * Now the avatar either runs or says why it cannot. This component owns that
 * decision so no caller has to: it asks the backend once whether the service
 * and a speech provider are both available, and renders the stream or the
 * offline panel accordingly.
 */
import { useCallback, useEffect, useState } from 'react';

import AvatarOffline, { AvatarPreview } from './AvatarOffline';
import SyncTalkStage from './SyncTalkStage';
import { STREAM_STATUS } from './useSyncTalkStream';
import { avatarStatus } from '../../api/avatar';

export default function AvatarStage({
  spokenText = '',
  isSpeaking = false,
  onSpeechEnd = null,
  audioMuted = false,
  onToggleMute = null,
  // Marketing surfaces want the tutor as an image, not a live session. A public
  // page must not open a GPU session for every visitor, and it must not show a
  // diagnostic either - "avatar unavailable" is a fine thing to tell a signed-in
  // student and a terrible thing to put on a landing page.
  preview = false,
}) {
  const [availability, setAvailability] = useState(null);
  const [streamFailed, setStreamFailed] = useState(false);

  useEffect(() => {
    if (preview) return undefined;
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
  }, [preview]);

  // Latched: once a stream has failed we stay offline for the rest of the
  // session rather than reconnecting to a box that is probably still down.
  const handleUnavailable = useCallback(() => setStreamFailed(true), []);
  const handleStatusChange = useCallback((status) => {
    if (status === STREAM_STATUS.LIVE) setStreamFailed(false);
  }, []);

  if (preview) return <AvatarPreview />;

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
    />
  );
}
