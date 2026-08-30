/** API calls. OWNER: Member 2. All requests go through the shared client. */
import client from './client';

export const listCourses = (params) => client.get('/api/courses', { params });
export const getCourse = (slug) => client.get(`/api/courses/${slug}`);
export const enroll = (courseId) => client.post(`/api/courses/${courseId}/enroll`);
export const myEnrollments = () => client.get('/api/me/enrollments');
export const myProgress = () => client.get('/api/me/progress');
export const myHistory = (params) => client.get('/api/me/history', { params });
