/** API calls. OWNER: Member 1. All requests go through the shared client. */
import client from './client';

export const listRecommendations = () => client.get('/api/recommendations');
export const dismissRecommendation = (id) => client.post(`/api/recommendations/${id}/dismiss`);
export const dailyPlan = () => client.get('/api/recommendations/daily-plan');
