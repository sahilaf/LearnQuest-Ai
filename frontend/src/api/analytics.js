/** API calls. OWNER: Member 4. All requests go through the shared client. */
import client from './client';

export const mySummary = () => client.get('/api/analytics/me/summary');
export const myActivity = (days = 56) => client.get('/api/analytics/me/activity', { params: { days } });
export const myMastery = () => client.get('/api/analytics/mastery/me');
export const adminOverview = () => client.get('/api/analytics/admin/overview');
