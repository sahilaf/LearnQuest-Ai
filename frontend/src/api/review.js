/**
 * Spaced-repetition review queue. OWNER: Member 1 (scheduler) / Member 2 (UI).
 * All requests go through the shared client. See plan.md 6.12.
 *
 * The queue schedules TOPICS, not questions: each review draws a question for
 * the topic, preferring one not shown last time, so a learner cannot memorise
 * the item instead of the idea. Items are interleaved so the same topic never
 * appears twice in a row.
 *
 * There is deliberately NO client-side fallback. The one that used to be here
 * marked any answer longer than three characters correct - typing "asdf" earned
 * "Clear and conceptually accurate answer" - and attached the same hardcoded
 * misconception about superkeys to every wrong answer, whatever the topic.
 * That directly contradicted what this project claims to do, so an honest error
 * is shown instead.
 */
import client from './client';

/** {items: [{id, topic_tag, topic_name, type, prompt, options, due_at,
 *            interval_days, streak}], total_due, next_due_at} */
export const getTodayReview = () => client.get('/api/review/today');

/**
 * Grade an answer, reschedule the topic, and update mastery.
 *
 * {item_id, is_correct, score_0_1, verdict, feedback, needs_review,
 *  misconception, next_due_at, interval_days, correct_answer}
 *
 * `needs_review` means the answer could not be graded confidently - it is NOT
 * marked wrong and the schedule is left alone. `misconception` is set only when
 * a wrong typed answer revealed a specific false belief; otherwise it is null.
 */
export const submitReviewAnswer = (itemId, { answer }) =>
  client.post(`/api/review/${itemId}/answer`, { answer });
