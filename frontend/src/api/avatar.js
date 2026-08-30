/** API calls. OWNER: Member 1. All requests go through the shared client. */
import client from './client';

export const avatarStatus = () => client.get('/api/avatar/status');
export const avatarConfig = () => client.get('/api/avatar/config');
export const speak = (text, expression) => client.post('/api/avatar/speak', { text, expression });
