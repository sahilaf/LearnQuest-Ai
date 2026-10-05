/** Live voice tutor. OWNER: Member 1. See backend app/routers/live.py. */

/** ws(s)://<api>/api/live/ws, derived from VITE_API_URL like every other call. */
export function liveSocketUrl() {
  const base = import.meta.env.VITE_API_URL || window.location.origin;
  return `${base.replace(/^http/, 'ws').replace(/\/$/, '')}/api/live/ws`;
}
