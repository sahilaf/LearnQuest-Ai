/**
 * AvatarStage - OWNER: Member 1. See plan.md 6.6.
 *
 * Tier A: renders a 2D sprite/SVG mouth or a Three.js morph-target head driven by
 * the viseme timeline. Tier B: renders the SyncTalk video stream when the backend
 * reports one. Same props either way - graceful degradation.
 */
export default function AvatarStage({
  expression = 'neutral',
  visemes = [],
  audioUrl = null,
  videoStreamUrl = null,
}) {
  // TODO(M1): week 1 spike - swap a mouth sprite per viseme against audio currentTime.
  // TODO(M1): week 3 - idle blink every 3-6s, head sway, expression state machine.
  if (videoStreamUrl) {
    return (
      <img
        src={videoStreamUrl}
        alt="AI tutor avatar"
        className="aspect-square w-full rounded-xl bg-slate-900 object-cover"
      />
    );
  }

  return (
    <div className="flex aspect-square w-full items-center justify-center rounded-xl bg-gradient-to-b from-primary-100 to-primary-50 dark:from-slate-800 dark:to-slate-900">
      <span className="text-sm text-slate-500">
        Avatar ({expression}) - {visemes.length} visemes
      </span>
    </div>
  );
}
