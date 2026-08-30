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
export const explain = (lessonId, selection) =>
  client.post('/api/tutor/explain', { lesson_id: lessonId, selection });

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
