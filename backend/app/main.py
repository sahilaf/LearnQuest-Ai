"""FastAPI entrypoint.

SHARED FILE - change only by agreement (plan.md 2.4).

All twelve routers are registered here already, one line each, so nobody has to
touch this file again. Build inside your own router module instead.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import database_is_configured
from app.routers import (
    admin,
    analytics,
    auth,
    avatar,
    courses,
    gamification,
    jobs,
    lessons,
    mastery,
    practice,
    progress,
    quizzes,
    recommendations,
    review,
    roadmap,
    tutor,
    users,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("learnquest")

app = FastAPI(
    title="LearnQuest AI",
    description="AI-Powered Personalized Learning Platform with a Real-Time Avatar Tutor",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Service health."},
        {"name": "auth", "description": "Authentication and session sync. (M3)"},
        {"name": "users", "description": "Profile and preferences. (M3)"},
        {"name": "admin", "description": "Admin panel: users, courses, uploads. (M3)"},
        {"name": "courses", "description": "Course catalog and enrollment. (M2/M3)"},
        {"name": "lessons", "description": "Lesson content and delivery. (M2)"},
        {"name": "progress", "description": "Lesson progress and learning history. (M2)"},
        {"name": "quizzes", "description": "Quiz attempts (M2) and AI generation (M1)."},
        {"name": "tutor", "description": "AI tutor conversations. (M1)"},
        {"name": "roadmap", "description": "AI-generated learning roadmaps. (M1)"},
        {"name": "mastery", "description": "Topic mastery and misconceptions. (M1)"},
        {"name": "jobs", "description": "Background AI generation jobs. (M1)"},
        {"name": "review", "description": "Spaced-repetition review queue. (M1)"},
        {"name": "practice", "description": "SQL practice problems, graded by running them. (M2/M1)"},
        {"name": "avatar", "description": "Avatar speech and lipsync payloads. (M1)"},
        {"name": "recommendations", "description": "Personalized recommendations. (M1)"},
        {"name": "gamification", "description": "XP, badges, streaks, challenges. (M4)"},
        {"name": "analytics", "description": "Learner and admin analytics. (M4)"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- routers: one line per module, do not reorder ---
app.include_router(auth.router)              # M3
app.include_router(users.router)             # M3
app.include_router(admin.router)             # M3
app.include_router(courses.router)           # M3 writes / M2 reads
app.include_router(lessons.router)           # M2
app.include_router(progress.router)          # M2
app.include_router(quizzes.router)           # M2 attempts + M1 generation
app.include_router(mastery.router)           # M1
app.include_router(jobs.router)              # M1
app.include_router(review.router)            # M1
app.include_router(practice.router)          # M2 UI / M1 runner
app.include_router(roadmap.router)           # M1
app.include_router(tutor.router)             # M1
app.include_router(avatar.router)            # M1
app.include_router(recommendations.router)   # M1
app.include_router(gamification.router)      # M4
app.include_router(analytics.router)         # M4


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {
        "status": "ok",
        "env": settings.app_env,
        "database_configured": database_is_configured(),
        "llm_provider": settings.llm_provider,
        "avatar_tier": "B" if settings.avatar_service_url else "A",
    }


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": "LearnQuest AI", "docs": "/docs", "health": "/api/health"}


@app.on_event("startup")
def _startup() -> None:
    logger.info("LearnQuest AI starting in %s mode", settings.app_env)

    # A restart mid-generation leaves rows stuck at "running" that nothing is
    # alive to finish, and a client would poll them forever.
    if database_is_configured():
        try:
            from app.database import get_session_factory
            from app.services.jobs import reap_stale_jobs

            db = get_session_factory()()
            try:
                reap_stale_jobs(db)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001 - never block startup on this
            logger.warning("Could not reap stale generation jobs: %s", exc)
    if not database_is_configured():
        logger.warning("DATABASE_URL is not set - endpoints that need the DB will fail.")
    if settings.llm_provider == "mock":
        logger.warning("LLM_PROVIDER=mock - the tutor returns canned responses.")
    if settings.dev_allow_anonymous and settings.is_production:
        # Refused rather than obeyed - see Settings.allow_anonymous. Logged
        # loudly because a deploy carrying this flag is a misconfiguration
        # someone needs to fix even though it is no longer dangerous.
        logger.error(
            "DEV_ALLOW_ANONYMOUS is true in production. Ignoring it; "
            "anonymous requests are refused. Remove it from the environment."
        )


@app.on_event("shutdown")
async def _shutdown() -> None:
    """Close the pooled LLM HTTP client so connections drain cleanly."""
    from app.services.llm_client import close_http_client

    await close_http_client()
    logger.info("LearnQuest AI shut down cleanly")
