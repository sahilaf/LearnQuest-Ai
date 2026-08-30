"""AI quiz generation. OWNER: Member 1. See plan.md 6.4."""


async def generate_quiz(
    db,
    *,
    lesson_id,
    user_id,
    num_questions: int = 5,
    difficulty: str = "auto",
    types: tuple[str, ...] = ("mcq", "true_false"),
):
    """Generate, validate and persist a quiz.

    Pipeline (plan.md 6.4):
      1. load lesson content_md + topic_tags
      2. difficulty="auto" -> from topic_mastery: <0.4 easy, 0.4-0.75 medium, >0.75 hard
      3. LLM call in JSON mode
      4. Pydantic validation, retry once, drop malformed questions (never 500)
      5. persist with source='ai_generated', return M2's exact quiz shape
      6. emit("quiz.generated", ...)

    Guardrails: correct_answer must be in options; no duplicate prompts;
    cap 10 questions; 20 generations per user per day.
    """
    raise NotImplementedError("TODO(M1): week 2")
