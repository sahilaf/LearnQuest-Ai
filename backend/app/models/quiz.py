"""quizzes, questions, quiz_attempts, attempt_answers.

OWNER: Member 2 (attempts) and Member 1 (AI-generated questions). Schema: plan.md 3.

TODO: attempt_answers.topic_tag is denormalised on purpose - copy it from
questions.topic_tag at submit time so mastery can be recomputed cheaply.
"""
