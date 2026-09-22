/** API calls. OWNER: Member 1. All requests go through the shared client. */
import client from './client';

export const createConversation = (body) => client.post('/api/tutor/conversations', body);
export const listConversations = (params) => client.get('/api/tutor/conversations', { params });
export const listMessages = (conversationId) =>
  client.get(`/api/tutor/conversations/${conversationId}/messages`);
export const sendMessage = (conversationId, content) =>
  client.post(`/api/tutor/conversations/${conversationId}/messages`, { content });
export const deleteConversation = (conversationId) =>
  client.delete(`/api/tutor/conversations/${conversationId}`);
/**
 * Explain a highlighted excerpt from a lesson.
 * `selection` is the text the student highlighted; `question` is what they
 * typed, if anything. They are separate fields because the backend prompt
 * frames `selection` as "the excerpt the student highlighted".
 */
export const explain = (lessonId, selection, question) =>
  client.post('/api/tutor/explain', { lesson_id: lessonId, selection, question });

/**
 * SSE token stream. EventSource cannot send an Authorization header, so pass the
 * token as a query param and verify it server-side (plan.md 6.3).
 */
export function streamMessage(conversationId, query, { onToken, onDone, onError }) {
  const base = import.meta.env.VITE_API_URL || '';
  const url = `${base}/api/tutor/conversations/${conversationId}/stream?q=${encodeURIComponent(query)}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    if (e.data === '[DONE]') {
      es.close();
      onDone?.();
      return;
    }
    onToken?.(e.data);
  };
  es.onerror = (err) => {
    es.close();
    onError?.(err);
  };

  return () => es.close();
}

/* --- Teach-Back: the student teaches Nova out of their own misconception. --- */

/** Misconceptions that are still standing, so still teachable. */
export const teachBackAvailable = () => client.get('/api/tutor/teachback/available');

/** Open a round. Omit topicTag to take the most recently captured belief. */
export const startTeachBack = (topicTag) =>
  client.post('/api/tutor/teachback/start', { topic_tag: topicTag ?? null });

export const getTeachBack = (sessionId) =>
  client.get(`/api/tutor/teachback/${sessionId}`);

/** Send an explanation. Nova pushes back or concedes. */
export const teachNova = (sessionId, message) =>
  client.post(`/api/tutor/teachback/${sessionId}/teach`, { message });

/** Nova re-takes the question. Her score is the student's grade. */
export const novaRetake = (sessionId) =>
  client.post(`/api/tutor/teachback/${sessionId}/retake`);
