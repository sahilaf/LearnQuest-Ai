import { describe, expect, it } from 'vitest';

import { splitForSpeech } from './SyncTalkStage';

const joined = (pieces) => pieces.join(' ').replace(/\s+/g, ' ').trim();

describe('splitForSpeech', () => {
  it('speaks the first sentence on its own, so the voice starts sooner', () => {
    const text = 'Binary search halves the list every step. With 1,024 items that is ten checks. Try it.';
    const pieces = splitForSpeech(text);
    expect(pieces[0]).toBe('Binary search halves the list every step.');
    expect(pieces).toHaveLength(2);
  });

  it('never splits inside a number like 3.14', () => {
    const pieces = splitForSpeech('Here is a fairly long opening sentence for the test. Use 3.14 as pi.');
    expect(pieces.some((p) => p.includes('3.14'))).toBe(true);
  });

  it('loses no words, whatever the length', () => {
    const text = 'word, '.repeat(400).trim();
    expect(joined(splitForSpeech(text))).toBe(text);
  });

  it('keeps every piece under the backend TTS cap (1200 chars)', () => {
    const pieces = splitForSpeech(`Hi. ${'A long sentence with many words in it. '.repeat(80)}`);
    pieces.forEach((p) => expect(p.length).toBeLessThanOrEqual(1200));
  });

  it('returns nothing for empty text', () => {
    expect(splitForSpeech('   ')).toEqual([]);
  });
});
