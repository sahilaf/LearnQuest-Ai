import { describe, expect, it } from 'vitest';

import { liveStateOf } from './LiveStatus';
import { LIVE_STATUS } from './useLiveConversation';

const call = (over) => ({
  status: LIVE_STATUS.LIVE, phase: 'listening', micMuted: false, userTalking: false, ...over,
});

describe('liveStateOf - whose turn is it', () => {
  it('is the student\'s turn when Redwan is waiting', () => {
    expect(liveStateOf(call())).toBe('turn');
  });
  it('shows listening while the student talks', () => {
    expect(liveStateOf(call({ userTalking: true }))).toBe('hearing');
  });
  it('shows thinking between the question and the answer', () => {
    expect(liveStateOf(call({ phase: 'thinking' }))).toBe('thinking');
  });
  it('speaking wins over everything else', () => {
    expect(liveStateOf(call({ phase: 'speaking', userTalking: true, micMuted: true }))).toBe('speaking');
  });
  it('says the mic is muted rather than inviting the student to talk', () => {
    expect(liveStateOf(call({ micMuted: true }))).toBe('muted');
  });
  it('shows connecting before the call is up', () => {
    expect(liveStateOf(call({ status: LIVE_STATUS.CONNECTING }))).toBe('connecting');
  });
});
