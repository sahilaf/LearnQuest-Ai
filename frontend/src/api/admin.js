/** API calls. OWNER: Member 3. All requests go through the shared client. */
import client from './client';

export const overview = () => client.get('/api/admin/overview');
export const listUsers = (params) => client.get('/api/admin/users', { params });
export const updateUser = (id, body) => client.patch(`/api/admin/users/${id}`, body);
export const createCourse = (body) => client.post('/api/admin/courses', body);
export const createLesson = (courseId, body) =>
  client.post(`/api/admin/courses/${courseId}/lessons`, body);
