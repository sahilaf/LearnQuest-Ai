/** API calls. OWNER: Member 3. All requests go through the shared client. */
import client from './client';

export const syncUser = () => client.post('/api/auth/sync');
export const getMe = () => client.get('/api/me');
export const updateMe = (body) => client.patch('/api/me', body);
