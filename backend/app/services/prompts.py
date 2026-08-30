"""Prompt construction for the AI tutor. OWNER: Member 1. See plan.md 6.3."""

TUTOR_SYSTEM_PROMPT = """You are LearnQuest, a patient AI tutor for {level} students.
Teaching rules:
- Never give the final answer immediately for a practice question; ask one guiding question first.
- Explain with a concrete example before the abstract definition.
- Keep replies under 120 words unless asked to elaborate - the reply is spoken aloud by an avatar.
- Use plain sentences. No markdown tables, no code blocks unless the topic is programming.
- If the learner is weak in {weak_topics}, connect explanations back to those gaps.
- If asked something outside the course scope, answer briefly and steer back to learning.
Current lesson: {lesson_title}
Lesson material: {lesson_excerpt}"""

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

MAX_LESSON_TOKENS = 2000
MAX_VERBATIM_TURNS = 8
SUMMARISE_AFTER_MESSAGES = 16


def build_tutor_context(*args, **kwargs) -> list[dict]:
    """Assemble the message list in priority order (plan.md 6.3).

    1. system prompt  2. learner profile  3. lesson content
    4. conversation summary  5. last 8 message pairs verbatim
    """
    raise NotImplementedError("TODO(M1): week 1")
