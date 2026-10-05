/**
 * Microphone -> 16 kHz 16-bit mono PCM chunks, for the live tutor.
 *
 * Gemini Live wants 16 kHz; browsers record at 44.1 or 48 kHz. An AudioWorklet
 * averages each block of input samples down to 16 kHz (a box filter - plenty
 * for speech) and posts ~100 ms chunks back to the page.
 *
 * Echo cancellation is on, but it is not relied on: the caller stops sending
 * while the tutor is talking, so the tutor never hears itself and
 * interrupts its own answer.
 */
const WORKLET = `
class Downsampler extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.ratio = sampleRate / 16000;
    this.acc = 0; this.count = 0; this.pos = 0;
    this.out = new Int16Array(1600);   // 100 ms at 16 kHz
    this.n = 0;
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i += 1) {
      this.acc += ch[i]; this.count += 1; this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const v = Math.max(-1, Math.min(1, this.acc / this.count));
        this.out[this.n++] = v < 0 ? v * 32768 : v * 32767;
        this.acc = 0; this.count = 0;
        if (this.n === this.out.length) {
          let peak = 0;
          for (let j = 0; j < this.n; j += 1) peak = Math.max(peak, Math.abs(this.out[j]));
          this.port.postMessage({ pcm: this.out.slice(0).buffer, level: peak / 32768 });
          this.n = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('lq-downsampler', Downsampler);
`;

export async function openMicStream(onChunk) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
  });
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const ctx = new AudioCtx();
  const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
  try {
    await ctx.audioWorklet.addModule(url);
  } finally {
    URL.revokeObjectURL(url);
  }
  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, 'lq-downsampler');
  node.port.onmessage = (event) => onChunk(event.data.pcm, event.data.level);
  source.connect(node);

  return {
    close() {
      node.port.onmessage = null;
      source.disconnect();
      node.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      ctx.close().catch(() => {});
    },
  };
}
