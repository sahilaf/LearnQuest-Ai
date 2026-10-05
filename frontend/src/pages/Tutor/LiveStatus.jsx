/**
 * LiveStatus - OWNER: Member 1.
 *
 * One visual language for where a live call is, used on the face, on the
 * voice orb and in the transcript header, so the student never has to guess
 * whose turn it is:
 *
 *   your turn     green, mic   - Redwan is waiting; speak
 *   hearing you   green, bars  - your voice is coming through
 *   thinking      amber, dots  - you finished; the answer is coming
 *   speaking      violet, wave - Redwan is talking; your mic is paused
 */
import { Mic } from 'lucide-react';

import { LIVE_STATUS } from './useLiveConversation';

export const LIVE_STATES = {
  idle: { label: 'Ready', hint: 'Waiting for you', tone: 'neutral' },
  connecting: { label: 'Connecting...', hint: 'Opening the line', tone: 'neutral' },
  turn: { label: 'Your turn', hint: 'Go ahead and speak', tone: 'go' },
  hearing: { label: 'Listening', hint: 'Keep going - Redwan is listening', tone: 'go' },
  muted: { label: 'Mic muted', hint: 'Unmute to talk, or type below', tone: 'neutral' },
  thinking: { label: 'Thinking', hint: 'Redwan is working out his answer', tone: 'wait' },
  speaking: { label: 'Redwan is speaking', hint: 'Your mic is paused - press Stop talking to cut in', tone: 'talk' },
};

export function liveStateOf(live) {
  if (live.status === LIVE_STATUS.CONNECTING) return 'connecting';
  if (live.phase === 'speaking') return 'speaking';
  if (live.phase === 'thinking') return 'thinking';
  if (live.micMuted) return 'muted';
  return live.userTalking ? 'hearing' : 'turn';
}

const TONE = {
  go: { text: 'text-easy-fg', dot: 'bg-easy', ring: 'border-easy/60', glow: 'rgb(var(--easy) / 0.22)', chip: 'bg-easy/15 border-easy/40' },
  wait: { text: 'text-medium-fg', dot: 'bg-medium', ring: 'border-medium/60', glow: 'rgb(var(--medium) / 0.2)', chip: 'bg-medium/15 border-medium/40' },
  talk: { text: 'text-primary-200', dot: 'bg-primary-400', ring: 'border-primary-400/70', glow: 'rgb(var(--primary-500) / 0.28)', chip: 'bg-primary-500/20 border-primary-400/40' },
  neutral: { text: 'text-muted', dot: 'bg-line-strong', ring: 'border-line-strong', glow: 'transparent', chip: 'bg-raised border-line' },
};

/** Three dots that pulse in turn: "working on it". */
export function ThinkingDots({ className = 'bg-medium' }) {
  return (
    <span className="inline-flex items-center gap-1" aria-hidden>
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className={`h-1.5 w-1.5 animate-bounce rounded-full ${className}`}
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

/** Bars that move: someone is talking. Driven by the mic level when given. */
export function TalkBars({ level = null, className = 'bg-primary-300', count = 5 }) {
  return (
    <span className="inline-flex h-4 items-center gap-0.5" aria-hidden>
      {Array.from({ length: count }, (_, i) => {
        const shape = [0.5, 0.8, 1, 0.8, 0.5][i % 5];
        return (
          <span
            key={i}
            className={`w-1 rounded-sm ${className} ${level === null ? 'animate-pulse' : ''}`}
            style={level === null
              ? { height: `${6 + shape * 10}px`, animationDelay: `${i * 120}ms` }
              : { height: `${Math.max(3, Math.min(16, 3 + level * 120 * shape))}px` }}
          />
        );
      })}
    </span>
  );
}

function StateIcon({ state, level }) {
  const tone = TONE[LIVE_STATES[state].tone];
  if (state === 'thinking') return <ThinkingDots />;
  if (state === 'speaking') return <TalkBars />;
  if (state === 'hearing') return <TalkBars level={level} className="bg-easy" />;
  if (state === 'turn') return <Mic className={`h-4 w-4 ${tone.text}`} />;
  return <span className={`h-2 w-2 rounded-full ${tone.dot}`} />;
}

/** Compact chip: transcript header, and laid over the avatar's video. */
export function LiveStatusChip({ state, level = 0, withHint = false, className = '' }) {
  const info = LIVE_STATES[state];
  const tone = TONE[info.tone];
  return (
    <div className={`inline-flex items-center gap-2.5 rounded-pill border px-3 py-1.5 backdrop-blur ${tone.chip} ${className}`}>
      <StateIcon state={state} level={level} />
      <span className={`whitespace-nowrap text-sm font-semibold ${tone.text}`}>{info.label}</span>
      {withHint && <span className="hidden whitespace-nowrap text-xs text-muted xl:inline">{info.hint}</span>}
    </div>
  );
}

/**
 * The tutor's presence when the avatar is not connected: a ring that breathes
 * with the state, so a voice-only call still has somewhere to look.
 */
export function VoiceOrb({ state, level = 0, onConnectAvatar = null }) {
  const info = LIVE_STATES[state];
  const tone = TONE[info.tone];
  const scale = state === 'hearing' ? 1 + Math.min(0.12, level * 0.8) : 1;
  return (
    <div className="panel w-full">
      <div className="panel-head">
        <span className="label">Redwan</span>
        <span className="text-2xs text-faint">Voice only</span>
      </div>
      <div className="flex aspect-square w-full flex-col items-center justify-center gap-6 bg-canvas p-6">
        <div className="relative flex items-center justify-center">
          <span
            className="absolute h-44 w-44 rounded-full transition-all duration-300"
            style={{ background: `radial-gradient(circle, ${tone.glow}, transparent 70%)` }}
          />
          <span
            className={`relative flex h-32 w-32 items-center justify-center rounded-full border-2 bg-surface transition-transform duration-150 ${tone.ring} ${
              state === 'speaking' || state === 'thinking' ? 'animate-pulse' : ''
            }`}
            style={{ transform: `scale(${scale})` }}
          >
            <span className="text-3xl font-semibold text-ink">R</span>
          </span>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-2">
            <StateIcon state={state} level={level} />
            <span className={`text-lg font-semibold ${tone.text}`}>{info.label}</span>
          </div>
          <p className="mt-1 text-sm text-muted">{info.hint}</p>
        </div>
        {onConnectAvatar && (
          <button
            type="button"
            onClick={onConnectAvatar}
            className="rounded border border-line px-3 py-1.5 text-xs text-muted transition-colors hover:border-muted hover:text-ink"
          >
            Connect avatar to see Redwan
          </button>
        )}
      </div>
    </div>
  );
}
