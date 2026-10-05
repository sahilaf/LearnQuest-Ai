/**
 * TutorStage - OWNER: Member 1.
 *
 * Redwan's place on the page, the same in every tab. With video connected it
 * is the live face (AvatarStage); without, a still of him. Either way one
 * status chip says what he is doing right now - including when he is talking
 * voice-only, so speech never comes from nowhere.
 *
 * Video is opt-in: nothing connects until the student presses "Connect video".
 */
import { Video, Volume2, VolumeX } from 'lucide-react';

import AvatarStage from '../../components/avatar/AvatarStage';
import { LiveStatusChip } from './LiveStatus';

function StillPresence({ state, level, onConnect, muted, onToggleMute, compact, fill }) {
  return (
    <div className={`panel ${fill ? 'flex w-full flex-col lg:h-full' : 'w-full'}`}>
      <div className="panel-head">
        <span className="label">Redwan</span>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onToggleMute}
            className="rounded p-1.5 text-muted transition-colors hover:bg-line hover:text-ink"
            title={muted ? 'Turn voice on' : 'Turn voice off'}
            aria-label={muted ? 'Turn voice on' : 'Turn voice off'}
          >
            {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
          <button
            type="button"
            onClick={onConnect}
            className="inline-flex items-center gap-1.5 rounded border border-line-strong px-2.5 py-1 text-xs font-medium text-body transition-colors hover:border-muted hover:text-ink"
          >
            <Video className="h-3.5 w-3.5" />
            Connect video
          </button>
        </div>
      </div>
      <div className={`relative w-full overflow-hidden bg-canvas ${fill ? 'aspect-[4/3] lg:aspect-auto lg:min-h-0 lg:flex-1' : `aspect-[4/3] ${compact ? '' : 'lg:aspect-square'}`}`}>
        <picture>
          <source srcSet="/landing/redwan.webp" type="image/webp" />
          <img
            src="/landing/redwan.jpg"
            alt="Redwan, your tutor"
            className={`h-full w-full object-cover object-top transition-opacity duration-300 ${
              state === 'speaking' ? 'opacity-90' : 'opacity-60'
            }`}
          />
        </picture>
        <span className="absolute right-3 top-3 rounded-pill bg-canvas/80 px-2 py-0.5 text-2xs text-muted backdrop-blur">
          Voice only
        </span>
        <div className="absolute inset-x-3 bottom-3">
          <LiveStatusChip state={state} level={level} />
        </div>
      </div>
    </div>
  );
}

export default function TutorStage({
  state = 'idle',
  level = 0,
  connected,
  onConnect,
  onDisconnect,
  onAvailabilityChange,
  controllerRef,
  avatarLine,
  onAvatarLineEnd,
  muted,
  onToggleMute,
  compact = false,
  fill = false,
}) {
  if (!connected) {
    return (
      <StillPresence
        state={state}
        level={level}
        onConnect={onConnect}
        muted={muted}
        onToggleMute={onToggleMute}
        compact={compact}
        fill={fill}
      />
    );
  }
  return (
    <AvatarStage
      connected
      onDisconnect={onDisconnect}
      onAvailabilityChange={onAvailabilityChange}
      controllerRef={controllerRef}
      spokenText={avatarLine.text}
      isSpeaking={avatarLine.speaking}
      onSpeechEnd={onAvatarLineEnd}
      audioMuted={muted}
      onToggleMute={onToggleMute}
      overlay={<LiveStatusChip state={state} level={level} />}
      compact={compact}
      fill={fill}
    />
  );
}
