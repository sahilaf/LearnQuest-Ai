"""user_stats, badges, user_badges, xp_events, daily_challenges,
user_challenges, notifications.

OWNER: Member 4. Schema: plan.md 3.

TODO(M4): every XP award writes an xp_events row - that table is the analytics
source of truth. Never mutate user_stats.xp without a matching event.
"""
