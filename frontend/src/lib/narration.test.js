import { describe, expect, it } from 'vitest';

import { CODE_CUE, planNarration } from './narration';

const words = (text) => ({ words: text.split(' ') });

describe('planNarration', () => {
  const plan = planNarration([
    words('Primary keys'),
    words('A primary key identifies a row. It is never null, and it is unique.'),
    { cue: CODE_CUE },
    words('That is all'),
  ]);

  it('says every word once, in order, ending headings with a pause', () => {
    const said = plan.chunks.map((c) => c.text).join(' ');
    expect(said).toBe(
      `Primary keys. A primary key identifies a row. It is never null, and it is unique. ${CODE_CUE} That is all.`,
    );
  });

  it('splits sentences at terminal punctuation and block ends', () => {
    const text = plan.sentences.map((s) => plan.units.slice(s.start, s.end + 1).map((u) => u.text).join(' '));
    expect(text).toEqual([
      'Primary keys',
      'A primary key identifies a row.',
      'It is never null, and it is unique.',
      CODE_CUE,
      'That is all',
    ]);
  });

  it('does not end a sentence at initials or abbreviations', () => {
    const p = planNarration([words('It was formulated by E.F. Codd in 1970, e.g. for banks. Then it spread.')]);
    const text = p.sentences.map((s) => p.units.slice(s.start, s.end + 1).map((u) => u.text).join(' '));
    expect(text).toEqual(['It was formulated by E.F. Codd in 1970, e.g. for banks.', 'Then it spread.']);
  });

  it('resumes from the start of the sentence a word is in', () => {
    const unique = plan.units.findIndex((u) => u.text === 'unique.');
    expect(plan.units[plan.sentenceStartOf(unique)].text).toBe('It');
  });

  it('maps time to words monotonically across a chunk', () => {
    const k = 0;
    const chunk = plan.chunks[k];
    let last = -1;
    for (let f = 0; f < 1; f += 0.01) {
      const u = plan.unitAt(k, f);
      expect(u).toBeGreaterThanOrEqual(last);
      expect(u).toBeLessThanOrEqual(chunk.end);
      last = u;
    }
    expect(plan.unitAt(k, 0)).toBe(chunk.start);
    expect(plan.unitAt(k, plan.fractionOf(k, chunk.start + 2))).toBe(chunk.start + 2);
  });

  it('keeps the first chunk short and the rest within the request limit', () => {
    const sentence = 'This sentence is about forty characters long.';
    const long = planNarration(Array.from({ length: 80 }, () => words(sentence)), { firstMax: 100, max: 500 });
    expect(long.chunks[0].text.length).toBeLessThanOrEqual(100);
    long.chunks.forEach((c) => expect(c.text.length).toBeLessThanOrEqual(500));
    // Whole sentences: every chunk ends on a sentence end.
    long.chunks.forEach((c) => expect(long.units[c.end].sentenceEnd).toBe(true));
    expect(long.chunks.length).toBeLessThan(12);
  });

  it('cuts one enormous sentence between words rather than dropping it', () => {
    const giant = planNarration([words(Array.from({ length: 400 }, () => 'word').join(' '))], { max: 300 });
    giant.chunks.forEach((c) => expect(c.text.length).toBeLessThanOrEqual(300));
    expect(giant.chunks.reduce((n, c) => n + c.end - c.start + 1, 0)).toBe(400);
  });
});
