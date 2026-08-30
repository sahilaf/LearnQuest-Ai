/**
 * ChatPanel - OWNER: Member 1. See plan.md 6.7.
 *
 * SSE streaming, typing indicator, light markdown, 'Explain this' entry point,
 * optional mic button via the Web Speech API.
 */
import { EmptyState } from '../ui';

export default function ChatPanel({ conversationId }) {
  // TODO(M1): week 1 non-streaming, week 2 swap to streamMessage() from api/tutor.js.
  return (
    <EmptyState
      title="Chat not built yet"
      description={`Conversation ${conversationId ?? '(new)'} - Member 1, plan.md 6.3.`}
    />
  );
}
