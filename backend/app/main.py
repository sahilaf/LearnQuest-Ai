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
    lessons,
    progress,
    quizzes,
    recommendations,
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
    if not database_is_configured():
        logger.warning("DATABASE_URL is not set - endpoints that need the DB will fail.")
    if settings.llm_provider == "mock":
        logger.warning("LLM_PROVIDER=mock - the tutor returns canned responses.")
    if settings.dev_allow_anonymous and settings.is_production:
        logger.error("DEV_ALLOW_ANONYMOUS is true in production. Turn it off.")
