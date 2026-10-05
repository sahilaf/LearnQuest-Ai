/**
 * Plays 16-bit mono PCM chunks back to back on the Web Audio clock.
 *
 * The tutor's voice when the avatar is not connected: the live tutor streams
 * chunks as Gemini produces them, and spoken lines from TTS arrive whole.
 * Either way each chunk is scheduled right after the previous one, so there
 * is no gap between them and no overlap.
 */
export function createPcmPlayer(sampleRate = 24000) {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const ctx = new AudioCtx({ sampleRate });
  const gain = ctx.createGain();
  gain.connect(ctx.destination);
  let nextStart = 0;
  let sources = [];

  return {
    /** Queue one chunk (ArrayBuffer of int16 PCM). */
    enqueue(buffer) {
      if (!buffer || buffer.byteLength < 2) return;
      const pcm = new Int16Array(buffer.slice(0, buffer.byteLength - (buffer.byteLength % 2)));
      const samples = new Float32Array(pcm.length);
      for (let i = 0; i < pcm.length; i += 1) samples[i] = pcm[i] / 32768;
      const audio = ctx.createBuffer(1, samples.length, sampleRate);
      audio.copyToChannel(samples, 0);
      const source = ctx.createBufferSource();
      source.buffer = audio;
      source.connect(gain);
      // Back to back while the queue holds; after running dry, restart with
      // a 0.25 s cushion so the next network hiccup does not cut a word.
      const startAt = nextStart > ctx.currentTime ? nextStart : ctx.currentTime + 0.25;
      source.start(startAt);
      nextStart = startAt + audio.duration;
      sources.push(source);
      source.onended = () => { sources = sources.filter((s) => s !== source); };
    },
    /** True while anything queued is still to be heard (plus a short tail for room echo). */
    isPlaying: () => ctx.currentTime < nextStart + 0.35,
    /** Seconds until the queue runs dry. */
    remaining: () => Math.max(0, nextStart - ctx.currentTime),
    /** Silence everything now (the student interrupted). */
    stop() {
      sources.forEach((s) => { try { s.stop(); } catch { /* already ended */ } });
      sources = [];
      nextStart = 0;
    },
    setMuted(muted) { gain.gain.value = muted ? 0 : 1; },
    resume: () => ctx.resume().catch(() => {}),
    close: () => ctx.close().catch(() => {}),
  };
}
