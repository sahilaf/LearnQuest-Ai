"""Prompt construction and context assembly for the AI tutor.

OWNER: Member 1 (AI Avatar Tutor & Intelligent Learning).
See plan.md §6.3, §6.6, §6.10.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai import Conversation, Message, TopicMastery
from app.models.course import Lesson
from app.models.gamification import UserStats

TUTOR_SYSTEM_PROMPT = """You are LearnQuest, a patient, encouraging AI tutor for {level} students.
Teaching rules:
- Never give the final answer immediately for a practice question; ask one guiding question first.
- Explain with a concrete, intuitive example before the abstract definition.
- Keep replies under 120 words unless specifically asked to elaborate - the reply is spoken aloud by an avatar.
- Use clear, plain sentences. No complex markdown tables, and no code blocks unless the topic is programming.
- If the learner is weak in {weak_topics}, connect explanations back to those specific gaps.
{misconceptions_section}
- If asked something outside the learning scope, answer briefly and steer back to learning.
Current lesson: {lesson_title}
Lesson material:
{lesson_excerpt}"""

QUIZ_GENERATION_PROMPT = """Generate {n} {difficulty} questions from the lesson below.
Allowed types: {types}.
Return ONLY valid JSON matching this schema:
{{"questions": [{{"type": "mcq", "prompt": "...", "options": ["a","b","c","d"],
  "correct_answer": "b", "explanation": "...", "topic_tag": "...", "difficulty": "medium"}}]}}
Rules:
- correct_answer MUST be one of the options for mcq questions.
- options MUST be null for types other than mcq.
- Never repeat a prompt within the same quiz.
- Every question must be answerable from the lesson below alone. Do not ask
  about anything the lesson does not teach, even if the topic tag suggests a
  wider subject.
- topic_tag must be one of: {topic_tags}

Lesson:
{lesson_content}"""

EXPLAIN_SELECTION_PROMPT = """You are LearnQuest, an AI tutor.
A student highlighted the following excerpt from the lesson "{lesson_title}":
"{selection}"

Provide a concise, intuitive explanation (under 90 words) using a simple everyday analogy.
Speak directly to the student."""

EXPLAIN_QUESTION_PROMPT = """You are LearnQuest, an AI tutor.
A student is reading the lesson "{lesson_title}".

Excerpt they are looking at:
"{selection}"

Their question:
"{question}"

Answer their question directly, in under 120 words, using a simple everyday
analogy. Speak to the student, not about them."""

MAX_LESSON_TOKENS = 2000
MAX_VERBATIM_TURNS = 8
SUMMARISE_AFTER_MESSAGES = 16


def build_tutor_context(
    db: Session | None,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
    current_lesson_id: uuid.UUID | None = None,
) -> list[dict[str, str]]:
    """Assemble the message list in priority order (plan.md 6.3).

    1. System prompt (personality, level, weak topics, misconceptions, lesson excerpt)
    2. Learner profile
    3. Conversation summary (if rolled up)
    4. The last 8 message pairs verbatim
    """
    level = "intermediate"
    weak_topics_list: list[str] = []
    misconceptions_list: list[str] = []
    lesson_title = "General Learning"
    lesson_excerpt = "No lesson attached to this conversation."
    conv_summary: str | None = None
    history_messages: list[Message] = []

    if db is not None:
        try:
            # 1. Learner stats
            stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            if stats:
                if stats.level <= 2:
                    level = "beginner"
                elif stats.level <= 6:
                    level = "intermediate"
                else:
                    level = "advanced"

            # 2. Topic mastery & misconceptions
            masteries = (
                db.query(TopicMastery)
                .filter(TopicMastery.user_id == user_id)
                .order_by(TopicMastery.mastery_score.asc())
                .limit(5)
                .all()
            )
            for m in masteries:
                if float(m.mastery_score) < 0.6:
                    weak_topics_list.append(m.topic_tag)
                if m.misconception:
                    misconceptions_list.append(f"- On '{m.topic_tag}': {m.misconception}")

            # 3. Lesson content
            target_lesson_id = current_lesson_id
            if not target_lesson_id and conversation_id:
                conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv:
                    target_lesson_id = conv.context_lesson_id
                    conv_summary = conv.summary

            if target_lesson_id:
                lesson = db.query(Lesson).filter(Lesson.id == target_lesson_id).first()
                if lesson:
                    lesson_title = lesson.title or "Lesson"
                    raw_content = lesson.content_md or ""
                    # Approx token truncation
                    lesson_excerpt = raw_content[: MAX_LESSON_TOKENS * 4]

            # 4. Message history
            if conversation_id:
                # Fetch recent messages ordered chronologically
                # Last 8 turns = 16 messages
                all_msgs = (
                    db.query(Message)
                    .filter(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                    .all()
                )
                if len(all_msgs) > (MAX_VERBATIM_TURNS * 2):
                    history_messages = all_msgs[-(MAX_VERBATIM_TURNS * 2) :]
                else:
                    history_messages = all_msgs
        except Exception:
            pass

    weak_topics_str = ", ".join(weak_topics_list) if weak_topics_list else "none recorded"
    misconceptions_section = ""
    if misconceptions_list:
        misconceptions_section = (
            "Specific misconceptions to address if relevant:\n"
            + "\n".join(misconceptions_list)
        )

    system_content = TUTOR_SYSTEM_PROMPT.format(
        level=level,
        weak_topics=weak_topics_str,
        misconceptions_section=misconceptions_section,
        lesson_title=lesson_title,
        lesson_excerpt=lesson_excerpt,
    )

    context_messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]

    if conv_summary:
        context_messages.append(
            {
                "role": "system",
                "content": f"Prior conversation summary (long-term memory): {conv_summary}",
            }
        )

    for msg in history_messages:
        context_messages.append({"role": msg.role, "content": msg.content})

    return context_messages


def generate_conversation_title(user_message: str) -> str:
    """Create a short, clean title for a conversation based on the first query."""
    clean = user_message.strip().replace("\n", " ")
    if len(clean) <= 40:
        return clean or "New conversation"
    return clean[:37].rsplit(" ", 1)[0] + "..."


# --------------------------------------------------------------------------- #
# Course generation (M1). See services/course_planner.py.
# --------------------------------------------------------------------------- #

COURSE_OUTLINE_PROMPT = """Design a short course for one learner.

Their goal: {goal}

Tag every lesson with one topic.
{topic_rules}
{topic_vocabulary}

Plan {n_lessons} lessons that build on each other in order. Each needs a title
and a two-sentence summary of what it teaches and why it comes at that point.

Return ONLY JSON:
{{"title": "...", "description": "one or two sentences",
  "subject": "...", "difficulty": "beginner" | "intermediate" | "advanced",
  "estimated_hours": 1,
  "lessons": [{{"title": "...", "topic_tag": "...", "topic_label": "...", "summary": "..."}}]}}"""

# Shared by every prompt that tags content, so the rule cannot drift between
# generated courses and uploaded notes.
TOPIC_RULES = """- If a topic in the list below genuinely matches the lesson, use its tag exactly.
- If none matches, propose a new tag in the form subject.topic - lowercase,
  underscores, e.g. os.process_scheduling or biology.cell_division - and give
  a short human-readable topic_label for it. Reuse the same new tag for every
  lesson on the same topic.
- NEVER use a tag from an unrelated subject just because it is on the list.
  Notes about operating systems must not be tagged as databases.
- Tag each lesson with the most specific concept it teaches. Mastery and
  mistakes are tracked per topic, so lessons on different concepts (e.g. race
  conditions vs semaphores) need different tags; share a tag only when two
  lessons genuinely teach the same concept.
- topic_label is required only for new tags; for existing tags repeat the label.

Existing topics:"""

LESSON_CONTENT_PROMPT = """Write one lesson in Markdown for a {difficulty} learner.

Course: {course_title}
Lesson {position} of {total}: {lesson_title}
What it should teach: {summary}
{prior_context}
Rules:
- Around 400-600 words. Long enough to actually teach, short enough to finish.
- Open with the idea in plain language before any formal definition.
- Use one concrete worked example. For a programming topic include a short
  fenced code block; otherwise use a small table or a worked case.
- End with a two-sentence recap of what the reader should now be able to do.
- Do not include the lesson title as a heading; it is shown above your text.
- Do not invent facts you are unsure of. If something is genuinely contested,
  say so plainly rather than picking a side and stating it as settled.

Return ONLY the Markdown. No JSON, no preamble."""


# --------------------------------------------------------------------------- #
# Uploaded notes -> course (M1 pipeline over M3's extraction).
# See services/notes_course.py.
# --------------------------------------------------------------------------- #

NOTES_OUTLINE_PROMPT = """A student uploaded their own study notes. Plan a short course that
teaches what the notes cover.

The notes are split into numbered chunks marked [[1]], [[2]], ... below.

Plan between {min_lessons} and {max_lessons} lessons in a sensible teaching order.
Each lesson needs:
- title: a clear lesson title. Never a page header, course code, university or
  instructor name, date, or exam instruction.
- summary: two sentences on what it teaches.
- chunks: the chunk numbers this lesson should be taught from.
- topic_tag and topic_label, following the rules below.

Ignore administrative material entirely: cover pages, exam rules, marks
schemes, instructor details, tables of contents, reference lists.

If the notes contain no study material at all, return {{"lessons": []}}.

Tag every lesson with one topic.
{topic_rules}
{topic_vocabulary}

Return ONLY JSON:
{{"title": "...", "description": "one or two sentences",
  "subject": "...", "difficulty": "beginner" | "intermediate" | "advanced",
  "lessons": [{{"title": "...", "summary": "...", "chunks": [1, 2],
               "topic_tag": "...", "topic_label": "..."}}]}}

Notes:
{notes}"""

NOTES_LESSON_PROMPT = """Write one lesson in Markdown that teaches the material below to a
{difficulty} student. The material comes from the student's own notes, which
are often terse slides or bullet points.

Course: {course_title}
Lesson {position} of {total}: {lesson_title}
What it should teach: {summary}
{prior_context}
Rules:
- Teach, do not transcribe. Explain each idea in plain language first, then
  give the formal definition.
- Stay faithful to the notes: cover what they cover and use their terminology
  and notation. Where they are terse, fill in the standard explanation a good
  textbook would give. Never contradict them; if something in them looks
  wrong, say so briefly instead of repeating it as fact.
- Include one worked example. For a programming topic use a short fenced code
  block; otherwise a small table or a step-by-step case.
- Add a "Key terms" section: each term with a one-line definition.
- End with a two-sentence recap of what the reader can now do.
- Around 400-700 words.
- Do not include the lesson title as a heading; it is shown above your text.
- Leave out anything administrative: page headers, course codes, names, dates.

Source notes:
<<<
{source}
>>>

Return ONLY the Markdown. No JSON, no preamble."""
