/**
 * useLessonNarration - OWNER: Member 1.
 *
 * Redwan reads the lesson aloud: through the avatar when video is connected,
 * otherwise voice only. The word being said is highlighted on the page, its
 * sentence more softly, and the page follows along.
 *
 * - The audio clock is the source of truth. Highlighting asks the voice how
 *   many seconds of narration have actually been heard, so it waits through
 *   network gaps and the avatar's start-up buffer instead of running ahead.
 * - Pause stops the voice at once. Play resumes from the start of the
 *   sentence it stopped in, from audio already downloaded - no new request.
 * - Highlights use the CSS Custom Highlight API: no spans are inserted into
 *   the Markdown React rendered, so React's DOM is never touched.
 * - Clicking a paragraph while narrating jumps there. Scrolling by hand
 *   stops the page following for a few seconds.
 *
 * Lesson audio is requested with purpose "lesson", so the backend keeps it on
 * disk: a lesson costs TTS quota once, not once per listen.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
/* global Highlight */ // CSS Custom Highlight API; guarded by highlightsSupported()

import { synthesizeSpeech } from '../../api/avatar';
import { planNarration, rangeFor, readBlocks } from '../../lib/narration';

const SAMPLE_RATE = 24000;
/** Resume a little before the sentence, so its first word is not clipped. */
const BACKUP_SECONDS = 0.15;
/** After the student scrolls by hand, leave the page alone this long. */
const FOLLOW_PAUSE_MS = 5000;
/** Passage handed to the live tutor when the student stops to ask. */
const PASSAGE_MAX_CHARS = 1400;

export const NARRATION = {
  IDLE: 'idle',
  LOADING: 'loading',
  PLAYING: 'playing',
  PAUSED: 'paused',
  ENDED: 'ended',
  ERROR: 'error',
};

const highlightsSupported = () => typeof CSS !== 'undefined' && Boolean(CSS.highlights) && typeof Highlight !== 'undefined';

export default function useLessonNarration({ containerRef, voice, contentKey }) {
  const [status, setStatus] = useState(NARRATION.IDLE);
  const [error, setError] = useState(null);
  // Re-rendered only when the spoken word changes.
  const [caption, setCaption] = useState(null); // { words: string[], active: number }
  const [progress, setProgress] = useState(0);
  // Speech has run dry mid-lesson while the next part downloads.
  const [buffering, setBuffering] = useState(false);

  const voiceRef = useRef(voice);
  voiceRef.current = voice;
  const statusRef = useRef(status);
  statusRef.current = status;
  const scriptRef = useRef(null); // { blocks, plan }
  const audioRef = useRef(new Map()); // chunk index -> Promise<ArrayBuffer>
  const runRef = useRef(0);
  const timelineRef = useRef([]); // [{ k, start, dur }] on the heard-seconds clock
  const doneSendingRef = useRef(false);
  const unitRef = useRef(0);
  const markedRef = useRef(null); // the block element marked as being read
  const rafRef = useRef(null);
  const followPausedUntilRef = useRef(0);

  /* ---- painting ---- */

  const clearPaint = useCallback(() => {
    if (highlightsSupported()) {
      CSS.highlights.delete('narration-word');
      CSS.highlights.delete('narration-sentence');
    }
    if (markedRef.current) delete markedRef.current.dataset.narrating;
    markedRef.current = null;
  }, []);

  const paint = useCallback((u) => {
    const script = scriptRef.current;
    if (!script) return;
    const { plan, blocks } = script;
    const unit = plan.units[u];
    if (!unit) return;
    const block = blocks[unit.block];
    const sentence = plan.sentences[unit.sentence];

    if (markedRef.current !== block.el) {
      if (markedRef.current) delete markedRef.current.dataset.narrating;
      block.el.dataset.narrating = highlightsSupported() ? 'block' : 'fallback';
      markedRef.current = block.el;
    }

    let wordRange = null;
    if (highlightsSupported() && unit.word != null) {
      wordRange = rangeFor(block, unit.word);
      const first = plan.units[sentence.start];
      const last = plan.units[sentence.end];
      const sentenceRange = rangeFor(block, first.word ?? unit.word, last.word ?? unit.word);
      if (wordRange) CSS.highlights.set('narration-word', new Highlight(wordRange));
      if (sentenceRange) CSS.highlights.set('narration-sentence', new Highlight(sentenceRange));
    } else if (highlightsSupported()) {
      CSS.highlights.delete('narration-word');
      CSS.highlights.delete('narration-sentence');
    }

    // Follow along: keep the spoken line in the upper-middle of the screen.
    if (performance.now() > followPausedUntilRef.current) {
      const rect = (wordRange || block.el).getBoundingClientRect();
      if (rect.top < 96 || rect.bottom > window.innerHeight * 0.72) {
        window.scrollTo({ top: window.scrollY + rect.top - window.innerHeight * 0.35, behavior: 'smooth' });
      }
    }

    const words = plan.units.slice(sentence.start, sentence.end + 1).map((x) => x.text);
    setCaption({ words, active: u - sentence.start });
    setProgress(plan.units.length > 1 ? u / (plan.units.length - 1) : 1);
  }, []);

  /* ---- the script and its audio ---- */

  const ensureScript = useCallback(() => {
    if (scriptRef.current) return scriptRef.current;
    const blocks = readBlocks(containerRef.current);
    if (!blocks.length) return null;
    scriptRef.current = { blocks, plan: planNarration(blocks) };
    return scriptRef.current;
  }, [containerRef]);

  const audioFor = useCallback((k) => {
    const cache = audioRef.current;
    if (!cache.has(k)) {
      const text = scriptRef.current.plan.chunks[k].text;
      const request = synthesizeSpeech(text, { purpose: 'lesson' });
      request.catch(() => cache.delete(k)); // a failed part can be retried
      cache.set(k, request);
    }
    return cache.get(k);
  }, []);

  /* ---- playback ---- */

  const halt = useCallback(() => {
    runRef.current += 1;
    cancelAnimationFrame(rafRef.current);
    voiceRef.current.stop();
    setBuffering(false);
  }, []);

  const tick = useCallback((id) => {
    if (id !== runRef.current) return;
    const { plan } = scriptRef.current;
    const timeline = timelineRef.current;
    const heard = voiceRef.current.heardSeconds();
    const entry = timeline.find((e) => heard >= e.start && heard < e.start + e.dur);
    if (entry) {
      setBuffering(false);
      const u = plan.unitAt(entry.k, (heard - entry.start) / entry.dur);
      if (u !== unitRef.current) {
        unitRef.current = u;
        paint(u);
      }
    } else {
      const last = timeline[timeline.length - 1];
      if (last && heard >= last.start + last.dur - 0.05) {
        if (doneSendingRef.current && last.k === plan.chunks.length - 1) {
          runRef.current += 1;
          clearPaint();
          setBuffering(false);
          setCaption(null);
          setProgress(1);
          setStatus(NARRATION.ENDED);
          unitRef.current = 0;
          return;
        }
        setBuffering(true);
      }
    }
    rafRef.current = requestAnimationFrame(() => tick(id));
  }, [paint, clearPaint]);

  const fail = useCallback((err) => {
    halt();
    setStatus(NARRATION.ERROR);
    setError(err?.status === 503
      ? 'Redwan cannot read aloud right now - speech is unavailable (daily voice quota, or no key). You can still read along.'
      : 'Could not load the narration. Check your connection and press Play to try again.');
  }, [halt]);

  /** Read from unit `from` (the start of its sentence) to the end. */
  const run = useCallback(async (from) => {
    const script = ensureScript();
    if (!script) return;
    const { plan } = script;
    halt();
    const id = runRef.current;
    setStatus(NARRATION.LOADING);
    setError(null);
    doneSendingRef.current = false;

    const startUnit = plan.sentenceStartOf(from);
    unitRef.current = startUnit;
    paint(startUnit);
    const k = plan.chunkOfUnit(startUnit);

    let pcm;
    try { pcm = await audioFor(k); } catch (err) { if (id === runRef.current) fail(err); return; }
    if (id !== runRef.current) return;

    const dur = pcm.byteLength / 2 / SAMPLE_RATE;
    const offset = Math.max(0, plan.fractionOf(k, startUnit) * dur - BACKUP_SECONDS);
    const offsetBytes = Math.floor(offset * SAMPLE_RATE) * 2;
    voiceRef.current.resetClock();
    // On the heard-seconds clock, chunk k "started" `offset` seconds ago.
    timelineRef.current = [{ k, start: -offset, dur }];
    setStatus(NARRATION.PLAYING);
    rafRef.current = requestAnimationFrame(() => tick(id));
    if (k + 1 < plan.chunks.length) audioFor(k + 1).catch(() => {});

    await voiceRef.current.playPcm(pcm.slice(offsetBytes));
    for (let j = k + 1; j < plan.chunks.length; j += 1) {
      if (id !== runRef.current) return;
      let next;
      try { next = await audioFor(j); } catch (err) { if (id === runRef.current) fail(err); return; }
      if (id !== runRef.current) return;
      if (j + 1 < plan.chunks.length) audioFor(j + 1).catch(() => {});
      const prev = timelineRef.current[timelineRef.current.length - 1];
      timelineRef.current.push({ k: j, start: prev.start + prev.dur, dur: next.byteLength / 2 / SAMPLE_RATE });
      await voiceRef.current.playPcm(next);
    }
    if (id === runRef.current) doneSendingRef.current = true;
  }, [ensureScript, halt, paint, audioFor, tick, fail]);

  /** Where reading should start: the top, or the first paragraph in view. */
  const startingUnit = useCallback(() => {
    const script = ensureScript();
    if (!script || window.scrollY < 200) return 0;
    const index = script.blocks.findIndex((b) => b.el.getBoundingClientRect().top >= 80);
    return index > 0 ? script.plan.blockFirstUnit[index] : 0;
  }, [ensureScript]);

  const play = useCallback(() => {
    const s = statusRef.current;
    if (s === NARRATION.PLAYING || s === NARRATION.LOADING) return;
    if (s === NARRATION.PAUSED || (s === NARRATION.ERROR && unitRef.current > 0)) run(unitRef.current);
    else run(startingUnit());
  }, [run, startingUnit]);

  const pause = useCallback(() => {
    const s = statusRef.current;
    if (s !== NARRATION.PLAYING && s !== NARRATION.LOADING) return;
    halt();
    setStatus(NARRATION.PAUSED);
  }, [halt]);

  /** Close narration: stop, clear the page. */
  const stop = useCallback(() => {
    halt();
    clearPaint();
    setCaption(null);
    setProgress(0);
    unitRef.current = 0;
    setStatus(NARRATION.IDLE);
  }, [halt, clearPaint]);

  /** The passage around where narration is - context for a live question. */
  const passage = useCallback(() => {
    const script = scriptRef.current;
    if (!script) return '';
    const unit = script.plan.units[unitRef.current];
    if (!unit) return '';
    const block = script.blocks[unit.block];
    const text = block.cue ? '' : block.words.join(' ');
    const sentence = script.plan.sentences[unit.sentence];
    const said = script.plan.units.slice(sentence.start, sentence.end + 1).map((x) => x.text).join(' ');
    return (text && text !== said ? `${said} (from: ${text})` : said).slice(0, PASSAGE_MAX_CHARS);
  }, []);

  /* ---- page wiring ---- */

  // A new lesson is a new script; whatever was playing stops.
  useEffect(() => {
    scriptRef.current = null;
    audioRef.current = new Map();
    return () => {
      runRef.current += 1;
      cancelAnimationFrame(rafRef.current);
      voiceRef.current.stop();
      clearPaint();
      setStatus(NARRATION.IDLE);
      setCaption(null);
      setProgress(0);
      unitRef.current = 0;
    };
  }, [contentKey, clearPaint]);

  // Scrolling by hand: stop following for a moment.
  useEffect(() => {
    const hold = () => { followPausedUntilRef.current = performance.now() + FOLLOW_PAUSE_MS; };
    const onKey = (e) => {
      if (['PageUp', 'PageDown', 'ArrowUp', 'ArrowDown', 'Home', 'End', ' '].includes(e.key)) hold();
    };
    window.addEventListener('wheel', hold, { passive: true });
    window.addEventListener('touchmove', hold, { passive: true });
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('wheel', hold);
      window.removeEventListener('touchmove', hold);
      window.removeEventListener('keydown', onKey);
    };
  }, []);

  // Click a paragraph while narrating to read from there.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;
    const onClick = (e) => {
      const s = statusRef.current;
      if (s !== NARRATION.PLAYING && s !== NARRATION.PAUSED && s !== NARRATION.LOADING) return;
      if (window.getSelection()?.toString().trim()) return; // selecting text, not jumping
      if (e.target.closest('a,button,input,textarea')) return;
      const script = scriptRef.current;
      if (!script) return;
      const index = script.blocks.findIndex((b) => b.el.contains(e.target));
      if (index < 0) return;
      followPausedUntilRef.current = 0;
      run(script.plan.blockFirstUnit[index]);
    };
    container.addEventListener('click', onClick);
    return () => container.removeEventListener('click', onClick);
  }, [containerRef, contentKey, run]);

  return {
    status, error, caption, progress, buffering,
    active: status !== NARRATION.IDLE,
    playing: status === NARRATION.PLAYING || status === NARRATION.LOADING,
    play, pause, stop, passage,
  };
}
