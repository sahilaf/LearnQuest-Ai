/**
 * LessonNarrator - OWNER: Member 1.
 *
 * Redwan reading the lesson, beside it: his face (or a still, voice only),
 * the sentence he is saying with the current word lit, and three controls -
 * Play/Pause, Ask (stop and ask him out loud), and Close.
 *
 * Asking pauses the reading and opens a live call that knows the passage you
 * stopped on. "Continue the lesson" ends the call and picks the reading up
 * at the start of that sentence.
 *
 * Two shapes: `panel` beside the lesson on wide screens, `bar` pinned to the
 * bottom of the screen on phones. Both drive the same state.
 */
import { Headphones, Mic, MicOff, Pause, Play, RotateCcw, X } from 'lucide-react';

import LivePanel from '../Tutor/LivePanel';
import { LIVE_STATES, liveStateOf } from '../Tutor/LiveStatus';
import TutorStage from '../Tutor/TutorStage';
import { LIVE_STATUS } from '../Tutor/useLiveConversation';
import { NARRATION } from './useLessonNarration';

/** The sentence being said, with the current word lit. */
function Caption({ caption, className = '' }) {
  if (!caption) return null;
  return (
    <p className={`text-sm leading-relaxed text-muted ${className}`} aria-hidden>
      {caption.words.map((word, i) => (
        <span
          key={i}
          className={i === caption.active ? 'rounded-sm bg-primary-500/30 text-ink' : i < caption.active ? 'text-body' : ''}
        >
          {word}{' '}
        </span>
      ))}
    </p>
  );
}

function statusLine(narration, inCall, live) {
  if (inCall) return LIVE_STATES[liveStateOf(live)];
  switch (narration.status) {
    case NARRATION.LOADING: return { label: 'Getting ready', hint: 'Preparing the first part - a few seconds' };
    case NARRATION.PLAYING:
      return narration.buffering
        ? { label: 'Loading the next part', hint: 'He carries on in a moment' }
        : { label: 'Reading', hint: 'Pause any time, or press Ask to stop and ask him' };
    case NARRATION.PAUSED: return { label: 'Paused', hint: 'Press Play to continue from this sentence' };
    case NARRATION.ENDED: return { label: 'Finished', hint: 'That is the whole lesson. Ready for the quiz?' };
    case NARRATION.ERROR: return { label: 'Stopped', hint: narration.error };
    default: return { label: 'Listen with Redwan', hint: 'He reads the lesson aloud and highlights each word as he says it.' };
  }
}

/** What the face's status chip shows. */
export function narratorStageState(narration, live) {
  const inCall = live.status === LIVE_STATUS.LIVE || live.status === LIVE_STATUS.CONNECTING;
  if (inCall) return liveStateOf(live);
  if (narration.status === NARRATION.LOADING || narration.buffering) return 'thinking';
  if (narration.status === NARRATION.PLAYING) return 'speaking';
  return 'idle';
}

function PlayButton({ narration, compact = false }) {
  const { playing, status } = narration;
  let label = 'Read this lesson to me';
  if (playing) label = 'Pause';
  else if (status === NARRATION.PAUSED) label = 'Play';
  else if (status === NARRATION.ENDED) label = 'Read it again';
  else if (status === NARRATION.ERROR) label = 'Try again';
  const Icon = playing ? Pause : status === NARRATION.ENDED || status === NARRATION.ERROR ? RotateCcw : Play;
  return (
    <button
      type="button"
      onClick={playing ? narration.pause : narration.play}
      className={`inline-flex items-center justify-center gap-2 rounded bg-primary-600 font-medium text-white transition-colors hover:bg-primary-500 ${
        compact ? 'h-10 w-10 shrink-0' : 'flex-1 px-4 py-2 text-sm'
      }`}
      aria-label={label}
      title={label}
    >
      <Icon className="h-4 w-4" />
      {!compact && label}
    </button>
  );
}

export default function LessonNarrator({
  variant = 'panel',
  narration,
  live,
  voice,
  onAsk,
  onContinue,
  avatar,
}) {
  const inCall = live.status === LIVE_STATUS.LIVE || live.status === LIVE_STATUS.CONNECTING;
  const line = statusLine(narration, inCall, live);
  const canAsk = narration.active && narration.status !== NARRATION.ERROR;

  /* ---- phones: a bar pinned to the bottom ---- */
  if (variant === 'bar') {
    if (!narration.active && !inCall) return null;
    // Above the app's 65px mobile tab bar (AppLayout), not on top of it.
    return (
      <div className="fixed inset-x-0 bottom-[65px] z-30 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur lg:hidden" role="region" aria-label="Lesson narration">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-ink">{line.label}</p>
            {inCall ? (
              <p className="truncate text-xs text-muted">{line.hint}</p>
            ) : (
              <div className="mt-1 h-1 overflow-hidden rounded-pill bg-line">
                <div className="h-full bg-primary-500 transition-[width] duration-300" style={{ width: `${Math.round(narration.progress * 100)}%` }} />
              </div>
            )}
          </div>
          {inCall ? (
            <>
              <button
                type="button"
                onClick={() => live.setMicMuted(!live.micMuted)}
                className="flex h-10 w-10 items-center justify-center rounded border border-line text-body"
                aria-label={live.micMuted ? 'Unmute mic' : 'Mute mic'}
              >
                {live.micMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              </button>
              <button type="button" onClick={onContinue} className="rounded bg-primary-600 px-3 py-2 text-sm font-medium text-white">
                Continue
              </button>
            </>
          ) : (
            <>
              {canAsk && (
                <button
                  type="button"
                  onClick={onAsk}
                  className="flex h-10 items-center gap-1.5 rounded border border-line px-3 text-sm text-body"
                >
                  <Mic className="h-4 w-4" /> Ask
                </button>
              )}
              <PlayButton narration={narration} compact />
              <button type="button" onClick={narration.stop} className="p-2 text-muted" aria-label="Close narration">
                <X className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  /* ---- wide screens: beside the lesson ---- */
  return (
    <div className="space-y-3">
      <TutorStage
        state={narratorStageState(narration, live)}
        level={live.level}
        connected={avatar.connected}
        onConnect={avatar.connect}
        onDisconnect={avatar.disconnect}
        onAvailabilityChange={avatar.setLive}
        controllerRef={avatar.ref}
        avatarLine={voice.avatarLine}
        onAvatarLineEnd={voice.onAvatarLineEnd}
        muted={avatar.muted}
        onToggleMute={avatar.toggleMute}
        compact
      />

      <div className="card space-y-3 p-4" role="status" aria-live="polite">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
              {!narration.active && !inCall && <Headphones className="h-4 w-4 text-primary-300" />}
              {line.label}
            </p>
            <p className={`mt-0.5 text-xs ${narration.status === NARRATION.ERROR && !inCall ? 'text-hard-fg' : 'text-muted'}`}>{line.hint}</p>
          </div>
          {narration.active && !inCall && (
            <button type="button" onClick={narration.stop} className="rounded p-1 text-muted transition-colors hover:bg-raised hover:text-ink" aria-label="Close narration" title="Stop reading">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {!inCall && <Caption caption={narration.caption} />}

        {narration.active && !inCall && (
          <div className="h-1 overflow-hidden rounded-pill bg-line" aria-label={`${Math.round(narration.progress * 100)}% read aloud`}>
            <div className="h-full bg-primary-500 transition-[width] duration-300" style={{ width: `${Math.round(narration.progress * 100)}%` }} />
          </div>
        )}

        {inCall ? (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onContinue}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-500"
            >
              <Play className="h-4 w-4" />
              Continue the lesson
            </button>
            <button
              type="button"
              onClick={() => live.setMicMuted(!live.micMuted)}
              disabled={live.status !== LIVE_STATUS.LIVE}
              className={`inline-flex items-center gap-1.5 rounded border px-3 py-2 text-sm transition-colors disabled:opacity-40 ${
                live.micMuted ? 'border-hard/50 text-hard-fg' : 'border-line text-body hover:text-ink'
              }`}
              aria-label={live.micMuted ? 'Unmute mic' : 'Mute mic'}
              title={live.micMuted ? 'Unmute mic' : 'Mute mic'}
            >
              {live.micMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <PlayButton narration={narration} />
            {canAsk && (
              <button
                type="button"
                onClick={onAsk}
                className="inline-flex items-center gap-1.5 rounded border border-line-strong px-3 py-2 text-sm font-medium text-body transition-colors hover:border-muted hover:text-ink"
                title="Pause and ask Redwan out loud"
              >
                <Mic className="h-4 w-4" />
                Ask
              </button>
            )}
          </div>
        )}

        {live.error && !inCall && <p className="text-xs text-hard-fg">{live.error}</p>}
        {narration.active && !inCall && (
          <p className="text-2xs text-faint">Tip: click any paragraph to read from there.</p>
        )}
      </div>

      {inCall && (
        <div className="card flex h-80 flex-col overflow-hidden">
          <LivePanel live={live} />
        </div>
      )}
    </div>
  );
}
