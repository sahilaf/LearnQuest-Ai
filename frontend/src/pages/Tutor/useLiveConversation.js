/**
 * useLiveConversation - OWNER: Member 1.
 *
 * A spoken conversation with the tutor over /api/live/ws (Gemini Live behind
 * it). The student talks; the tutor answers out loud ~1.5s after they stop.
 *
 * Turn-taking is half duplex on purpose: the microphone is not forwarded while
 * the tutor is talking. Browser echo cancellation does not reliably cover
 * audio played through Web Audio, and a tutor that hears its own voice
 * interrupts itself mid-sentence. To cut in, the student presses "Stop
 * talking", which silences the reply and opens the mic.
 *
 * Every finished exchange is saved server-side into the current
 * conversation, so the Chat tab sees what was said here.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { getAccessToken } from '../../api/client';
import { liveSocketUrl } from '../../api/live';
import { openMicStream } from '../../lib/micStream';

export const LIVE_STATUS = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LIVE: 'live',
  ERROR: 'error',
};

let turnSeq = 0;

/** Mic level (0..1) that counts as the student talking. */
const VOICE_LEVEL = 0.06;

/** A pause shorter than this is between words, not the end of a question. */
const TALK_HOLD_MS = 700;

export default function useLiveConversation({ voice }) {
  const [status, setStatus] = useState(LIVE_STATUS.IDLE);
  const [error, setError] = useState(null);
  const [turns, setTurns] = useState([]);
  const [phase, setPhase] = useState('listening'); // listening | thinking | speaking
  const [micMuted, setMicMuted] = useState(false);
  const [level, setLevel] = useState(0);
  // The student is mid-sentence. Held through short pauses between words so
  // the status does not flicker between "listening" and "your turn".
  const [userTalking, setUserTalking] = useState(false);

  const wsRef = useRef(null);
  const micRef = useRef(null);
  const voiceRef = useRef(voice);
  voiceRef.current = voice;
  const statusRef = useRef(status);
  statusRef.current = status;
  const micMutedRef = useRef(micMuted);
  micMutedRef.current = micMuted;
  // Reply audio is arriving for the current turn.
  const receivingRef = useRef(false);
  // The student stopped the reply; ignore its remaining audio until the turn ends.
  const droppingRef = useRef(false);
  // The student said something and the tutor has not started answering yet.
  const awaitingRef = useRef(false);
  // Which turn a transcript delta belongs to; null starts a new bubble.
  const openTurnRef = useRef({ user: null, tutor: null });
  const endedByUserRef = useRef(false);
  // Voice activity on the student's side, to show "thinking" the moment they
  // stop talking - the transcript only arrives ~1 s later.
  const voicedMsRef = useRef(0);
  const lastVoiceAtRef = useRef(0);

  // Decide which bubble the text belongs to *before* calling setTurns: React
  // (in StrictMode, i.e. every dev run) calls updaters twice, and an updater
  // that moved openTurnRef discarded its own new bubble on the second call -
  // the live transcript silently never appeared. Found by the E2E suite.
  const appendTranscript = useCallback((role, text) => {
    const openId = openTurnRef.current[role];
    if (openId != null) {
      setTurns((prev) => prev.map((t) => (t.id === openId ? { ...t, text: t.text + text } : t)));
      return;
    }
    turnSeq += 1;
    const id = turnSeq;
    openTurnRef.current[role] = id;
    setTurns((prev) => [...prev, { id, role, text: text.replace(/^\s+/, '') }]);
  }, []);

  const cleanup = useCallback(() => {
    micRef.current?.close();
    micRef.current = null;
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws) {
      ws.onclose = null;
      ws.onmessage = null;
      ws.onerror = null;
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'end' }));
      if (ws.readyState <= WebSocket.OPEN) ws.close();
    }
    receivingRef.current = false;
    droppingRef.current = false;
    awaitingRef.current = false;
    voiceRef.current.stop();
    setLevel(0);
  }, []);

  const fail = useCallback((message) => {
    cleanup();
    setError(message);
    setStatus(LIVE_STATUS.ERROR);
  }, [cleanup]);

  const handleControl = useCallback((event) => {
    switch (event.type) {
      case 'ready':
        setStatus(LIVE_STATUS.LIVE);
        break;
      case 'transcript':
        // Bubbles stay open for the whole exchange and close at turn_complete:
        // Gemini sometimes sends the end of what the student said after the
        // reply has begun, and that belongs in the student's bubble above,
        // not in a new one under the answer.
        if (event.role === 'user' && !receivingRef.current) awaitingRef.current = true;
        if (!(event.role === 'tutor' && droppingRef.current)) {
          appendTranscript(event.role, event.text);
        }
        break;
      case 'interrupted':
        voiceRef.current.stop();
        receivingRef.current = false;
        openTurnRef.current = { user: null, tutor: null };
        break;
      case 'turn_complete':
        voicedMsRef.current = 0;
        if (!droppingRef.current) voiceRef.current.endStream();
        receivingRef.current = false;
        droppingRef.current = false;
        awaitingRef.current = false;
        openTurnRef.current = { user: null, tutor: null };
        break;
      case 'error':
        fail(event.message || 'The live tutor stopped.');
        break;
      default:
    }
  }, [appendTranscript, fail]);

  // `reading`: the lesson passage the student paused on, for the tutor's context.
  const start = useCallback(async (conversationRef, { reading = null } = {}) => {
    if (statusRef.current === LIVE_STATUS.CONNECTING || statusRef.current === LIVE_STATUS.LIVE) return;
    setError(null);
    setTurns([]);
    openTurnRef.current = { user: null, tutor: null };
    endedByUserRef.current = false;
    setStatus(LIVE_STATUS.CONNECTING);

    // The microphone first: if it is blocked there is no point opening a call.
    try {
      micRef.current = await openMicStream((pcm, peak) => {
        setLevel(peak);
        const ws = wsRef.current;
        if (statusRef.current !== LIVE_STATUS.LIVE || ws?.readyState !== WebSocket.OPEN) return;
        if (micMutedRef.current || receivingRef.current || voiceRef.current.isAudible()) return;
        if (peak > VOICE_LEVEL) {
          voicedMsRef.current += 100;
          lastVoiceAtRef.current = performance.now();
        }
        ws.send(pcm);
      });
    } catch {
      fail('Microphone access was blocked. Allow it in the browser to talk to the tutor.');
      return;
    }

    let token = null;
    try { token = await getAccessToken(); } catch { /* the backend decides */ }

    const ws = new WebSocket(liveSocketUrl());
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;
    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'start', token, conversation: conversationRef ?? null, ...(reading ? { reading } : {}),
      }));
    };
    ws.onmessage = (msg) => {
      if (typeof msg.data === 'string') {
        try { handleControl(JSON.parse(msg.data)); } catch { /* not ours */ }
        return;
      }
      if (droppingRef.current) return;
      receivingRef.current = true;
      awaitingRef.current = false;
      voiceRef.current.streamChunk(msg.data);
    };
    ws.onerror = () => fail('Could not reach the live tutor.');
    ws.onclose = () => {
      if (!endedByUserRef.current && wsRef.current === ws) fail('The live conversation was disconnected.');
    };
  }, [fail, handleControl]);

  const stop = useCallback(() => {
    endedByUserRef.current = true;
    cleanup();
    setStatus(LIVE_STATUS.IDLE);
  }, [cleanup]);

  /** Cut the tutor off and hand the floor back to the student. */
  const interrupt = useCallback(() => {
    if (receivingRef.current) droppingRef.current = true;
    receivingRef.current = false;
    voiceRef.current.stop();
  }, []);

  /** Type instead of talking, mid-call. */
  const sendText = useCallback((text) => {
    const ws = wsRef.current;
    if (!text.trim() || ws?.readyState !== WebSocket.OPEN) return;
    interrupt();
    openTurnRef.current = { user: null, tutor: null };
    appendTranscript('user', text.trim());
    openTurnRef.current.user = null;
    awaitingRef.current = true;
    ws.send(JSON.stringify({ type: 'text', text: text.trim() }));
  }, [appendTranscript, interrupt]);

  // Derive what the tutor is doing for the status line.
  useEffect(() => {
    if (status !== LIVE_STATUS.LIVE) return undefined;
    const id = setInterval(() => {
      const sinceVoice = performance.now() - lastVoiceAtRef.current;
      // Spoke for a moment, then went quiet: the server will take it as a
      // finished question. Give up on that after a while (it was noise).
      const justAsked = voicedMsRef.current >= 400 && sinceVoice >= TALK_HOLD_MS && sinceVoice < 6000;
      setUserTalking(sinceVoice < TALK_HOLD_MS && !receivingRef.current);
      if (receivingRef.current || voiceRef.current.isAudible()) {
        voicedMsRef.current = 0;
        setPhase('speaking');
      } else if (awaitingRef.current || justAsked) setPhase('thinking');
      else {
        if (sinceVoice >= 6000) voicedMsRef.current = 0;
        setPhase('listening');
      }
    }, 200);
    return () => clearInterval(id);
  }, [status]);

  // Leaving the page ends the call.
  useEffect(() => () => { endedByUserRef.current = true; cleanup(); }, [cleanup]);

  return {
    status, error, turns, phase, level, micMuted, userTalking,
    setMicMuted, start, stop, interrupt, sendText,
  };
}
