"""conversations, messages, topic_mastery, recommendations, review_items.

OWNER: Member 1. Schema: plan.md 3.

TODO(M1): messages.visemes is JSONB holding the avatar playback timeline:
    [{"t": 0.00, "v": "sil"}, {"t": 0.08, "v": "AA"}]
conversations.summary is the rolling long-term memory (plan.md 6.3).

topic_mastery.misconception is the most important column in the project (plan.md 3.1,
6.10): the plain-English sentence describing what the learner believes that is wrong.
The tutor explains THAT, not the topic. Keep it under ~200 chars - it goes into every
prompt for the topic. Write nothing rather than inventing one.

review_items is the daily queue (plan.md 3.3). It schedules TOPICS, not stored
questions - the question is generated fresh each time so learners cannot memorise the
item instead of the idea.
"""
