/** API calls. OWNER: Member 4. All requests go through the shared client. */
import client from './client';

export const myStats = () => client.get('/api/me/stats');
export const myBadges = () => client.get('/api/me/badges');
export const todaysChallenges = () => client.get('/api/challenges/today');
export const claimChallenge = (id) => client.post(`/api/challenges/${id}/claim`);
export const leaderboard = (params) => client.get('/api/leaderboard', { params });
export const notifications = () => client.get('/api/notifications');
export const markRead = (id) => client.post(`/api/notifications/${id}/read`);
