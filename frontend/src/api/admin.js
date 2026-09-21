/** API calls. OWNER: Member 3. All requests go through the shared client. */
import client from './client';

export const overview = () => client.get('/api/admin/overview');

export const listUsers = (params) => client.get('/api/admin/users', { params });
export const updateUser = (id, body) => client.patch(`/api/admin/users/${id}`, body);

export const listCourses = (params) => client.get('/api/admin/courses', { params });
export const getCourse = (id) => client.get(`/api/admin/courses/${id}`);
export const createCourse = (body) => client.post('/api/admin/courses', body);
export const updateCourse = (id, body) => client.patch(`/api/admin/courses/${id}`, body);
export const deleteCourse = (id) => client.delete(`/api/admin/courses/${id}`);

export const createLesson = (courseId, body) =>
  client.post(`/api/admin/courses/${courseId}/lessons`, body);
export const updateLesson = (lessonId, body) =>
  client.patch(`/api/admin/lessons/${lessonId}`, body);
export const deleteLesson = (lessonId) =>
  client.delete(`/api/admin/lessons/${lessonId}`);
export const publishLesson = (lessonId) =>
  client.post(`/api/admin/lessons/${lessonId}/publish`);

export const uploadAdminFile = (formData) =>
  client.post('/api/admin/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
