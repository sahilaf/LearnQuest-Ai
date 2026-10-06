/**
 * LessonNarrator - OWNER: Member 1.
 *
 * Redwan's half of the lesson page: his face (or a still, voice only) and one
 * card that always answers "what is happening, and what can I press?".
 *
 * - Before starting, the card explains the three controls in plain words.
 * - While reading: what he is doing, the sentence he is saying with the
 *   current word lit, progress, and Pause / Ask / Stop.
 * - While asking: a live call that knows the passage you stopped on, its
 *   transcript, and "Continue the lesson", which picks the reading up at the
 *   start of that sentence.
 *
 * On phones the face is left out (voice only) so the text keeps the screen;
 * the card sits above the lesson.
 */
import { Hand, Headphones, Mic, MicOff, Pause, Play, RotateCcw, Square } from 'lucide-react';

import LivePanel from '../Tutor/LivePanel';
import { LIVE_STATES, liveStateOf } from '../Tutor/LiveStatus';
import TutorStage from '../Tutor/TutorStage';
import { LIVE_STATUS } from '../Tutor/useLiveConversation';
import { NARRATION } from './useLessonNarration';

/** Words shown around the spoken one - always fits the caption's three lines. */
const CAPTION_WORDS = 20;

/**
 * The sentence being said, with the current word lit. A fixed-height box
 * showing a window of words that moves with the voice: a caption that grew
 * and shrank with each sentence resized the video above it, and the page
 * jumped up and down while Redwan read.
 */
function Caption({ caption }) {
  let words = [];
  let start = 0;
  if (caption) {
    start = Math.max(0, Math.min(caption.active - 6, caption.words.length - CAPTION_WORDS));
    words = caption.words.slice(start, start + CAPTION_WORDS);
  }
  const more = caption && start + CAPTION_WORDS < caption.words.length;
  return (
    <p className="h-[5.25rem] overflow-hidden rounded border border-line bg-canvas px-3 py-2.5 text-sm leading-relaxed text-muted" aria-hidden>
      {start > 0 && '... '}
      {words.map((word, i) => {
        const index = start + i;
        return (
          <span
            key={index}
            className={index === caption.active ? 'rounded-sm bg-primary-500/30 text-ink' : index < caption.active ? 'text-body' : ''}
          >
            {word}{' '}
          </span>
        );
      })}
      {more && '...'}
    </p>
  );
}

function statusLine(narration, inCall, live) {
  if (inCall) return LIVE_STATES[liveStateOf(live)];
  switch (narration.status) {
    case NARRATION.LOADING: return { label: 'Getting ready', hint: 'Preparing his voice - a few seconds.' };
    case NARRATION.PLAYING:
      return narration.buffering
        ? { label: 'Loading the next part', hint: 'He carries on in a moment.' }
        : { label: 'Reading', hint: 'Follow the highlighted word in the text.' };
    case NARRATION.PAUSED: return { label: 'Paused', hint: 'Play continues from the start of this sentence.' };
    case NARRATION.ENDED: return { label: 'Finished', hint: 'That was the whole lesson. Try the quiz at the end of the text.' };
    case NARRATION.ERROR: return { label: 'Stopped', hint: narration.error };
    default: return null;
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

const PRIMARY = 'inline-flex items-center justify-center gap-2 rounded bg-primary-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-primary-500 disabled:opacity-50';
const SECONDARY = 'inline-flex items-center justify-center gap-1.5 rounded border border-line-strong px-3 py-2.5 text-sm font-medium text-body transition-colors hover:border-muted hover:text-ink disabled:opacity-40';

/** Before anything starts: what this is and how to use it, in three lines. */
function HowItWorks({ onStart, canRead, preparing }) {
  const steps = [
    { icon: Play, title: 'Play', body: 'Redwan reads the lesson aloud. The word he is saying lights up in the text.' },
    { icon: Hand, title: 'Ask', body: 'Did not get something? Press Ask and say your question out loud.' },
    { icon: RotateCcw, title: 'Continue', body: 'He picks up from the same sentence.' },
  ];
  return (
    <div className="space-y-3 lg:space-y-4">
      <div>
        <p className="flex items-center gap-2 text-base font-semibold text-ink">
          <Headphones className="h-4 w-4 text-primary-300" />
          Listen with Redwan
        </p>
        <p className="mt-1 text-sm text-muted lg:hidden">
          He reads the lesson aloud and lights up each word. Press Ask any time to question him.
        </p>
        <p className="mt-1 hidden text-sm text-muted lg:block">Let your tutor read this lesson to you, and stop him any time to ask.</p>
      </div>
      {/* The full how-to on wide screens; phones keep the room for the text. */}
      <ol className="hidden space-y-2.5 lg:block">
        {steps.map(({ icon: Icon, title, body }) => (
          <li key={title} className="flex gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-line bg-raised text-body">
              <Icon className="h-3.5 w-3.5" />
            </span>
            <p className="text-sm leading-snug text-muted"><span className="font-medium text-ink">{title}. </span>{body}</p>
          </li>
        ))}
      </ol>
      <button type="button" onClick={onStart} disabled={!canRead || preparing} className={`${PRIMARY} w-full`}>
        {preparing ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
        ) : (
          <Play className="h-4 w-4" />
        )}
        {preparing ? 'Connecting Redwan...' : 'Start listening'}
      </button>
    </div>
  );
}

export default function LessonNarrator({
  narration, live, voice, onAsk, onContinue, onStart, preparing = false, avatar, canRead = true,
}) {
  const inCall = live.status === LIVE_STATUS.LIVE || live.status === LIVE_STATUS.CONNECTING;
  const line = statusLine(narration, inCall, live);
  const started = narration.active || inCall;
  const percent = Math.round(narration.progress * 100);

  let card;
  if (!started) {
    card = <HowItWorks onStart={onStart} canRead={canRead} preparing={preparing} />;
  } else if (inCall) {
    card = (
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div>
          <p className="text-base font-semibold text-ink">{line.label}</p>
          <p className="mt-0.5 truncate text-sm text-muted">{line.hint}</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onContinue} className={`${PRIMARY} flex-1`}>
            <Play className="h-4 w-4" />
            Continue the lesson
          </button>
          <button
            type="button"
            onClick={() => live.setMicMuted(!live.micMuted)}
            disabled={live.status !== LIVE_STATUS.LIVE}
            className={`${SECONDARY} ${live.micMuted ? 'border-hard/50 text-hard-fg' : ''}`}
            aria-label={live.micMuted ? 'Unmute mic' : 'Mute mic'}
            title={live.micMuted ? 'Unmute mic' : 'Mute mic'}
          >
            {live.micMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          </button>
        </div>
        <div className="-mx-4 -mb-4 flex min-h-0 flex-1 flex-col border-t border-line">
          <LivePanel live={live} />
        </div>
      </div>
    );
  } else {
    const { playing, status } = narration;
    const restart = status === NARRATION.ENDED || status === NARRATION.ERROR;
    let playLabel = 'Play';
    if (playing) playLabel = 'Pause';
    else if (status === NARRATION.ENDED) playLabel = 'Read it again';
    else if (status === NARRATION.ERROR) playLabel = 'Try again';
    const PlayIcon = playing ? Pause : restart ? RotateCcw : Play;
    card = (
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-base font-semibold text-ink">{line.label}</p>
            <p
              className={`mt-0.5 text-sm ${status === NARRATION.ERROR ? 'text-hard-fg line-clamp-2' : 'truncate text-muted'}`}
              title={line.hint}
            >
              {line.hint}
            </p>
          </div>
          <span className="shrink-0 font-mono text-xs text-muted">{percent}%</span>
        </div>

        <div className="h-1 overflow-hidden rounded-pill bg-line" aria-label={`${percent}% read aloud`}>
          <div className="h-full bg-primary-500 transition-[width] duration-300" style={{ width: `${percent}%` }} />
        </div>

        <div className="hidden lg:block"><Caption caption={narration.caption} /></div>

        <div className="flex gap-2">
          <button type="button" onClick={playing ? narration.pause : narration.play} className={`${PRIMARY} flex-1`} aria-label={playLabel}>
            <PlayIcon className="h-4 w-4" />
            {playLabel}
          </button>
          {status !== NARRATION.ERROR && (
            <button type="button" onClick={onAsk} className={SECONDARY} title="Pause and ask Redwan out loud">
              <Mic className="h-4 w-4" />
              Ask
            </button>
          )}
          <button type="button" onClick={narration.stop} className={SECONDARY} aria-label="Close narration" title="Stop listening">
            <Square className="h-3.5 w-3.5" />
          </button>
        </div>

        <p className={`hidden truncate text-xs lg:block ${live.error ? 'text-hard-fg' : 'text-faint'}`}>
          {live.error || 'Tip: click any paragraph to read from there.'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 lg:h-full">
      {/* The face: half the screen on wide screens; left out on phones. */}
      <div className="hidden min-h-0 flex-1 lg:flex lg:flex-col">
        <TutorStage
          state={preparing ? 'connecting' : narratorStageState(narration, live)}
          level={live.level}
          connected={avatar.connected}
          onDisconnect={avatar.disconnect}
          showConnect={false}
          onReady={avatar.onReady}
          onOffline={avatar.onOffline}
          controllerRef={avatar.ref}
          avatarLine={voice.avatarLine}
          onAvatarLineEnd={voice.onAvatarLineEnd}
          muted={avatar.muted}
          onToggleMute={avatar.toggleMute}
          fill
        />
      </div>

      {/* One fixed size on wide screens, whatever the card shows, so the
          face above never resizes - not between sentences, not when a call
          starts. On phones only a call makes it taller (for its transcript). */}
      <div
        className={`card flex shrink-0 flex-col overflow-hidden p-4 lg:h-80 ${inCall ? 'h-80' : ''}`}
        role="status"
        aria-live="polite"
      >
        {card}
      </div>
    </div>
  );
}
