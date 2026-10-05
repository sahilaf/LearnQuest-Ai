/**
 * useTutorVoice - OWNER: Member 1.
 *
 * One voice for the whole tutor page, whichever tab is talking. It goes
 * through the avatar when the student has connected it and can see it, and
 * straight to the speakers otherwise - same male voice either way, so the
 * tutor sounds like one person across Live and Chat.
 *
 * Two kinds of speech:
 *   - text ("Listen" in Chat): synthesized by /api/avatar/speech
 *   - a live stream (the Live tab): PCM chunks from Gemini Live as they arrive
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { synthesizeSpeech } from '../../api/avatar';
import { splitForSpeech } from '../../components/avatar/SyncTalkStage';
import { createPcmPlayer } from '../../lib/pcmPlayer';

const SAMPLE_RATE = 24000;

export default function useTutorVoice({ avatarRef, useAvatar, muted }) {
  // Text the avatar should say; AvatarStage synthesizes and lip-syncs it.
  const [avatarLine, setAvatarLine] = useState({ text: '', speaking: false });
  const [synthesizing, setSynthesizing] = useState(false);
  const playerRef = useRef(null);
  const lineRef = useRef(0);
  const useAvatarRef = useRef(useAvatar);
  useAvatarRef.current = useAvatar;

  const player = useCallback(() => {
    if (!playerRef.current) playerRef.current = createPcmPlayer(SAMPLE_RATE);
    playerRef.current.resume();
    return playerRef.current;
  }, []);

  useEffect(() => { playerRef.current?.setMuted(muted); }, [muted]);
  useEffect(() => () => playerRef.current?.close(), []);

  const viaAvatar = () => Boolean(useAvatarRef.current && avatarRef.current);

  /** Stop whatever is being said, on either path. */
  const stop = useCallback(() => {
    lineRef.current += 1;
    setSynthesizing(false);
    setAvatarLine({ text: '', speaking: false });
    avatarRef.current?.stopNow();
    playerRef.current?.stop();
  }, [avatarRef]);

  /** Speak a line of text in the tutor's voice. */
  const speakText = useCallback(async (text) => {
    if (!text?.trim()) return;
    stop();
    if (viaAvatar()) {
      setAvatarLine({ text, speaking: true });
      return;
    }
    const line = lineRef.current;
    const pieces = splitForSpeech(text);
    // Both pieces requested at once; played in order (see SyncTalkStage).
    const pending = pieces.slice(0, 2).map((p) => synthesizeSpeech(p).catch(() => null));
    setSynthesizing(true);
    for (let i = 0; i < pieces.length; i += 1) {
      if (i >= 2) pending.push(synthesizeSpeech(pieces[i]).catch(() => null));
      const pcm = await pending[i];
      if (line !== lineRef.current) return;
      setSynthesizing(false);
      if (pcm) player().enqueue(pcm);
    }
  }, [player, stop]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Live tutor audio, chunk by chunk. */
  const streamChunk = useCallback((chunk) => {
    if (viaAvatar()) avatarRef.current.streamAudio(chunk, SAMPLE_RATE);
    else player().enqueue(chunk);
  }, [avatarRef, player]); // eslint-disable-line react-hooks/exhaustive-deps

  /** The live tutor finished a reply. */
  const endStream = useCallback(() => {
    avatarRef.current?.endStream(SAMPLE_RATE);
  }, [avatarRef]);

  /** Whether the tutor is talking (or about to) - the live mic stays shut then. */
  const isAudible = useCallback(() => {
    if (avatarRef.current?.isAudible()) return true;
    return Boolean(playerRef.current?.isPlaying());
  }, [avatarRef]);

  const onAvatarLineEnd = useCallback(() => {
    setAvatarLine((prev) => ({ ...prev, speaking: false }));
  }, []);

  return {
    speakText, stop, streamChunk, endStream, isAudible,
    synthesizing, avatarLine, onAvatarLineEnd,
  };
}
