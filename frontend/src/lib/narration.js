/**
 * Lesson narration: what to say, in which pieces, and which word is being
 * said at any moment. OWNER: Member 1. Used by pages/Lesson/useLessonNarration.
 *
 * The lesson is read from the rendered page, not the Markdown, so nothing
 * like "##" or "**" is ever spoken, and every word knows where it sits in
 * the page (for highlighting).
 *
 * Why chunks
 * ----------
 * Each chunk is one TTS request. The free Gemini tier allows ~10 requests a
 * day per model, so a lesson goes out in a handful of large chunks rather
 * than one per sentence; the first is short so the voice starts quickly.
 *
 * Word timing
 * -----------
 * TTS returns audio, not word timestamps. Within a chunk each word is given a
 * share of the audio by its length, plus a pause after punctuation and at the
 * end of a paragraph - roughly how a speaker paces. With the audio clock as
 * the source of truth that keeps the highlight on the spoken word to within
 * a word or so, which is what reading along needs.
 */

const TERMINAL = /[.!?]["')\]]*$/;
const SOFT_PAUSE = /[,;:]["')\]]*$/;
// A full stop that does not end a sentence: initials ("E.F.", "e.g.", "i.e.")
// and the usual abbreviations.
const ABBREVIATION = /^(?:[A-Za-z]\.){1,4}$|^(?:etc|vs|Mr|Mrs|Ms|Dr|Prof|approx|incl|fig|no)\.$/i;
// A sentence after it starts with a capital, a digit or an opening quote.
const STARTS_SENTENCE = /^["'([]?[A-Z0-9]/;

const endsSentence = (text, next) => {
  if (!TERMINAL.test(text)) return false;
  if (/[!?]["')\]]*$/.test(text)) return true;
  return !ABBREVIATION.test(text) && (!next || STARTS_SENTENCE.test(next));
};

/** What a code block is replaced with in speech: reading code aloud helps no one. */
export const CODE_CUE = 'Have a look at the code example here.';

/** Block-level elements, one block of narration each. */
const BLOCK_SELECTOR = 'h1,h2,h3,h4,h5,h6,p,li,blockquote,td,th,pre,figcaption,dt,dd';

/**
 * Plan narration from blocks of words.
 *
 * blocks: [{ words: string[] }] or [{ cue: string }] (said, not highlighted).
 * Returns units (words and cues in order), chunks (one TTS request each) and
 * lookups between them.
 */
export function planNarration(blocks, { firstMax = 260, max = 1000 } = {}) {
  const units = [];
  const blockFirstUnit = [];
  blocks.forEach((block, b) => {
    blockFirstUnit[b] = units.length;
    if (block.cue) {
      units.push({ text: block.cue, block: b, word: null, blockEnd: true, sentenceEnd: true });
      return;
    }
    block.words.forEach((text, i) => {
      const blockEnd = i === block.words.length - 1;
      units.push({
        text, block: b, word: i, blockEnd, sentenceEnd: blockEnd || endsSentence(text, block.words[i + 1]),
      });
    });
  });

  // Sentences: runs of units ending at a sentence end.
  const sentences = [];
  let start = 0;
  units.forEach((unit, u) => {
    unit.sentence = sentences.length;
    if (unit.sentenceEnd) {
      sentences.push({ start, end: u });
      start = u + 1;
    }
  });

  // What each unit sounds like, and its share of the time.
  const spoken = (unit) => (unit.blockEnd && !TERMINAL.test(unit.text) ? `${unit.text}.` : unit.text);
  const weight = (unit) => {
    let w = unit.text.length + 1;
    if (unit.sentenceEnd) w += 8;
    else if (SOFT_PAUSE.test(unit.text)) w += 4;
    if (unit.blockEnd) w += 6;
    return w;
  };

  // Chunks: whole sentences, up to the limit; the first one short.
  const chunks = [];
  let current = null;
  const open = (u) => { current = { start: u, end: u - 1, length: 0 }; chunks.push(current); };
  // The current chunk's soft limit: short for the first, so speech starts fast.
  const limit = () => (chunks.length === 1 ? firstMax : max);
  sentences.forEach((sentence) => {
    const length = units.slice(sentence.start, sentence.end + 1)
      .reduce((n, unit) => n + spoken(unit).length + 1, 0);
    if (!current || (current.length > 0 && current.length + length > limit())) open(sentence.start);
    // A sentence longer than a whole chunk is cut between words.
    for (let u = sentence.start; u <= sentence.end; u += 1) {
      const add = spoken(units[u]).length + 1;
      if (current.length > 0 && current.length + add > max) open(u);
      current.length += add;
      current.end = u;
    }
  });

  chunks.forEach((chunk) => {
    let at = 0;
    chunk.weights = [];
    for (let u = chunk.start; u <= chunk.end; u += 1) {
      const w = weight(units[u]);
      chunk.weights.push([at, at + w]);
      at += w;
    }
    chunk.total = at || 1;
    chunk.text = units.slice(chunk.start, chunk.end + 1).map(spoken).join(' ');
  });

  const chunkOfUnit = (u) => chunks.findIndex((c) => u >= c.start && u <= c.end);

  return {
    units,
    sentences,
    chunks,
    blockFirstUnit,
    chunkOfUnit,
    /** The first unit of the sentence `u` is in - where a resume starts. */
    sentenceStartOf: (u) => sentences[units[Math.max(0, Math.min(u, units.length - 1))]?.sentence ?? 0]?.start ?? 0,
    /** Where in its chunk's audio unit `u` starts, 0..1. */
    fractionOf(k, u) {
      const chunk = chunks[k];
      return chunk.weights[u - chunk.start][0] / chunk.total;
    },
    /** The unit being said `fraction` of the way through chunk `k`. */
    unitAt(k, fraction) {
      const chunk = chunks[k];
      const target = Math.max(0, Math.min(0.9999, fraction)) * chunk.total;
      let lo = 0;
      let hi = chunk.weights.length - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (chunk.weights[mid][0] <= target) lo = mid;
        else hi = mid - 1;
      }
      return chunk.start + lo;
    },
  };
}

/**
 * Read a rendered lesson into blocks of words, each word with the DOM range
 * it covers. Text split across nodes ("**bold**er") stays one word.
 */
export function readBlocks(container) {
  const blocks = [];
  if (!container) return blocks;
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let current = null;
  let open = false; // the last word ran to the end of its text node

  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const el = node.parentElement?.closest(BLOCK_SELECTOR);
    if (!el || !container.contains(el) || node.parentElement.closest('[aria-hidden="true"]')) continue;

    if (el.tagName === 'PRE') {
      if (!current || current.el !== el) {
        current = { el, cue: CODE_CUE, words: [], ranges: [] };
        blocks.push(current);
      }
      open = false;
      continue;
    }
    if (!current || current.el !== el) {
      current = { el, words: [], ranges: [] };
      blocks.push(current);
      open = false;
    }

    const text = node.data;
    const re = /\S+/g;
    let match = re.exec(text);
    if (!match) { open = false; continue; }
    while (match) {
      const end = match.index + match[0].length;
      const last = current.words.length - 1;
      if (match.index === 0 && open && last >= 0) {
        current.words[last] += match[0];
        current.ranges[last].end = { node, offset: end };
      } else {
        current.words.push(match[0]);
        current.ranges.push({ start: { node, offset: match.index }, end: { node, offset: end } });
      }
      open = end === text.length;
      match = re.exec(text);
    }
  }
  return blocks.filter((block) => block.cue || block.words.length);
}

/** A DOM Range for one word, or for a run of words in one block. */
export function rangeFor(block, fromWord, toWord = fromWord) {
  const first = block?.ranges?.[fromWord];
  const last = block?.ranges?.[toWord];
  if (!first || !last) return null;
  try {
    const range = document.createRange();
    range.setStart(first.start.node, first.start.offset);
    range.setEnd(last.end.node, last.end.offset);
    return range;
  } catch {
    return null; // the page changed under us
  }
}
