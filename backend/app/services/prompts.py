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
