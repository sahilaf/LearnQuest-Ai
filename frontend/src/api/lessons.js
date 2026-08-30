/** API calls. OWNER: Member 2. All requests go through the shared client. */
import client from './client';

export const getLesson = (lessonId) => client.get(`/api/lessons/${lessonId}`);
export const updateProgress = (lessonId, body) =>
  client.post(`/api/lessons/${lessonId}/progress`, body);
