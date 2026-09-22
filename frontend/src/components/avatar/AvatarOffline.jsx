/**
 * AvatarOffline - OWNER: Member 1. See plan.md §6.6.
 *
 * What you get instead of the tutor's face when the avatar cannot run.
 *
 * This exists because most of the team has no GPU. The avatar needs the
 * SyncTalk service reachable *and* a speech provider, and on a teammate's
 * laptop neither is true. A black canvas there reads as a bug and gets filed as
 * one, so this says plainly what is missing and confirms that everything else
 * on the page still works.
 *
 * It never shows a retry button: nothing the student can do in the browser
 * starts a GPU service, and a button that cannot work is worse than no button.
 */
import { Sparkles, VideoOff } from 'lucide-react';

/** Backend `reason` strings are diagnostics. Say something a human can act on. */
const FRIENDLY = {
  'AVATAR_SERVICE_URL is not set': 'The avatar service is not configured on this machine.',
  'Avatar service is not reachable': 'The avatar service is not running.',
  'Avatar service is still loading': 'The avatar service is still starting up.',
};

export default function AvatarOffline({ reason = null, compact = false }) {
  const message = FRIENDLY[reason]
    || (reason?.startsWith('No speech provider')
      ? 'No speech provider is configured, so the tutor has no voice.'
      : 'The avatar is unavailable right now.');

  return (
    <div className="panel aspect-square w-full">
      <div className="panel-head">
        <span className="label">Tutor</span>
        <span className="flex items-center gap-2 text-2xs font-medium text-faint">
          <span className="h-1.5 w-1.5 rounded-full bg-faint" />
          Offline
        </span>
      </div>

      <div
        className={`flex h-full flex-col items-center justify-center text-center ${
          compact ? 'p-5' : 'p-7'
        }`}
      >
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-line bg-raised text-faint">
          <VideoOff className="h-5 w-5" />
        </div>

        <p className="text-lg font-semibold text-ink">Avatar offline</p>
        <p className="mt-1.5 max-w-[18rem] text-base text-muted">{message}</p>
        <p className="mt-3 max-w-[18rem] text-sm text-faint">
          Everything else works — the tutor still answers in the chat, and
          Teach-Back runs normally.
        </p>

        {reason && (
          <code className="mt-4 max-w-full truncate rounded border border-line bg-canvas px-2.5 py-1.5 font-mono text-2xs text-faint">
            {reason}
          </code>
        )}
      </div>
    </div>
  );
}

/**
 * The tutor panel as a still, for marketing surfaces.
 *
 * Deliberately not `AvatarOffline`: a landing page visitor has no idea what an
 * avatar service is, so telling them one is unreachable is noise at best and
 * looks broken at worst. This shows the same framed panel with the product's
 * own language and never opens a session.
 */
export function AvatarPreview() {
  // Headless on purpose: this is always placed inside a frame the page already
  // provides, and two stacked title strips saying the same thing is the kind of
  // detail that makes a layout look unconsidered.
  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-lg border border-line bg-canvas">
      <div className="relative flex h-full items-center justify-center p-6">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_38%,rgb(var(--primary-600)/0.22),transparent_62%)]" />
        <div className="relative flex flex-col items-center text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-pill border border-primary-500/40 bg-primary-500/10 text-primary-300">
            <Sparkles className="h-7 w-7" />
          </span>
          <p className="mt-4 font-display text-xl text-ink">She explains it your way</p>
          <p className="mt-1.5 max-w-[15rem] text-sm text-muted">
            A real face that answers out loud — and learns what you keep getting wrong.
          </p>
        </div>
      </div>
    </div>
  );
}
