/**
 * useLipsync - OWNER: Member 1. See plan.md 6.7.
 *
 * Maps an <audio> element's currentTime onto the viseme timeline via
 * requestAnimationFrame and returns the viseme that should be showing right now.
 *
 * Timeline shape: [{ t: 0.00, v: 'sil' }, { t: 0.08, v: 'AA' }]
 */
import { useEffect, useRef, useState } from 'react';

export default function useLipsync(audioRef, visemes = []) {
  const [current, setCurrent] = useState('sil');
  const frameRef = useRef(null);

  useEffect(() => {
    if (!audioRef?.current || visemes.length === 0) return undefined;

    const tick = () => {
      const t = audioRef.current?.currentTime ?? 0;
      // TODO(M1): binary search instead of findLast once timelines get long.
      const active = [...visemes].reverse().find((v) => v.t <= t);
      setCurrent(active?.v ?? 'sil');
      frameRef.current = requestAnimationFrame(tick);
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [audioRef, visemes]);

  return current;
}
