/** API calls. OWNER: Member 1. All requests go through the shared client. */
import client from './client';

/**
 * Whether the avatar can render AND speak: {online, speech, reason?, fps, sample_rate}.
 * Both halves are required - the service renders frames only in response to
 * audio, so no speech provider means a frozen face.
 */
export const avatarStatus = () => client.get('/api/avatar/status');

export const avatarConfig = () => client.get('/api/avatar/config');

/**
 * Open a SyncTalk session and get its WebSocket URLs.
 *
 * Proxied through our backend because the avatar service registers no CORS
 * middleware, so the browser cannot call its /session endpoint directly. The
 * WebSocket handshake that follows is not subject to CORS, so the stream itself
 * connects straight to the GPU box.
 */
export const avatarSession = () => client.post('/api/avatar/session');

/**
 * Synthesize speech, returning raw 16-bit mono PCM as an ArrayBuffer.
 *
 * Binary rather than JSON: a few seconds of 24 kHz PCM is ~200 KB and base64
 * would inflate it by a third for nothing. The backend guarantees the rate
 * matches the avatar stream, so the caller can forward these bytes straight to
 * SyncTalk without resampling.
 *
 * Rejects with 503 when no speech provider is configured.
 */
export const synthesizeSpeech = (text) =>
  client.post('/api/avatar/speech', { text }, { responseType: 'arraybuffer' });
