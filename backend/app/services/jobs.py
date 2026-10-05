"""Background generation jobs. OWNER: Member 1.

Generation is too slow to do inside a request. Measured 2026-09-27: one
lesson-sized completion takes ~8s, so a six-lesson course is around 100s, while
`frontend/src/api/client.js` gives up at 30s. Anything generative therefore
creates a job, returns its id immediately, and the client polls.

Scope, deliberately
-------------------
A row, an asyncio task and a poll endpoint. Not a queue. A real queue is the
right answer for real traffic, but it is a whole piece of infrastructure this
project does not otherwise need, and the one failure it would buy us - a job
lost when the process restarts - is handled by `reap_stale_jobs()` at startup
instead of by a broker.

Each job runs on its OWN database session. The request's session is closed as
soon as the response is sent, so a task that kept using it would fail on its
first query a second later.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

logger = logging.getLogger("learnquest.jobs")

# Generation is billed per call and the free tier is a per-day, per-model quota
# shared with the tutor, misconception capture. This cap is what
# stops one enthusiastic student consuming the whole day's budget.
DAILY_JOBS_PER_USER = 20

# A job still "running" after this long did not survive a restart.
STALE_AFTER_MINUTES = 15

KINDS = ("quiz", "course")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobLimitReached(RuntimeError):
    """Raised when a user has used their daily generation allowance."""


def jobs_used_today(db, user_id: uuid.UUID) -> int:
    from app.models.ai import GenerationJob

    since = _now() - timedelta(days=1)
    return (
        db.query(GenerationJob)
        .filter(
            GenerationJob.user_id == user_id,
            GenerationJob.created_at >= since,
            # A job that failed for our reasons should not cost the student
            # part of their allowance.
            GenerationJob.status != "failed",
        )
        .count()
    )


def create_job(db, user_id: uuid.UUID, kind: str, params: dict[str, Any]):
    """Record a queued job. Raises JobLimitReached when over the daily cap."""
    from app.models.ai import GenerationJob

    if kind not in KINDS:
        raise ValueError(f"unknown job kind {kind!r}")

    used = jobs_used_today(db, user_id)
    if used >= DAILY_JOBS_PER_USER:
        raise JobLimitReached(
            f"You have used your {DAILY_JOBS_PER_USER} generations for today. "
            "They reset in 24 hours."
        )

    job = GenerationJob(
        user_id=user_id,
        kind=kind,
        status="queued",
        progress=0,
        params=params or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Queued %s job %s for user %s (%d/%d today)",
                kind, job.id, user_id, used + 1, DAILY_JOBS_PER_USER)
    return job


def get_job(db, job_id: uuid.UUID, user_id: uuid.UUID):
    """A job, scoped to its owner. None when it is missing or someone else's."""
    from app.models.ai import GenerationJob

    return (
        db.query(GenerationJob)
        .filter(GenerationJob.id == job_id, GenerationJob.user_id == user_id)
        .first()
    )


def set_progress(db, job_id: uuid.UUID, progress: int) -> None:
    """Coarse progress, safe to call from inside a running job."""
    from app.models.ai import GenerationJob

    try:
        db.query(GenerationJob).filter(GenerationJob.id == job_id).update(
            {"progress": max(0, min(100, int(progress)))}
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - progress is cosmetic
        logger.debug("Could not update progress for %s: %s", job_id, exc)
        db.rollback()


async def run_job(
    job_id: uuid.UUID,
    work: Callable[[Any, Any], Awaitable[dict[str, Any]]],
) -> None:
    """Execute `work(db, job)` on a fresh session and record the outcome.

    Never raises. A job that fails records why, in language a student can read,
    and the poll endpoint hands that back - an exception escaping here would
    leave the row stuck at "running" forever with nothing to show for it.
    """
    from app.database import get_session_factory
    from app.models.ai import GenerationJob

    db = get_session_factory()()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if job is None:
            logger.warning("Job %s vanished before it ran", job_id)
            return

        job.status = "running"
        job.started_at = _now()
        db.commit()

        try:
            result = await work(db, job)
            job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            job.status = "succeeded"
            job.progress = 100
            job.result = result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s failed", job_id)
            db.rollback()
            job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            if job is not None:
                job.status = "failed"
                job.error = _student_facing_error(exc)
        finally:
            if job is not None:
                job.finished_at = _now()
                db.commit()
    finally:
        db.close()


def _student_facing_error(exc: Exception) -> str:
    """Turn an exception into something worth showing a learner.

    They cannot act on a stack trace, and "429 Too Many Requests" tells them
    nothing about what to do next.
    """
    text = str(exc)
    if "429" in text or "quota" in text.lower():
        return "The AI is over its request limit right now. Try again in a few minutes."
    if "503" in text or "unavailable" in text.lower() or "overloaded" in text.lower():
        return "The AI service is busy right now. Nothing was lost - try again in a minute."
    if "timeout" in text.lower() or "timed out" in text.lower():
        return "Generating this took too long. Try again."
    return "Something went wrong while generating this. Try again."


def schedule(job_id: uuid.UUID, work: Callable[[Any, Any], Awaitable[dict[str, Any]]]) -> None:
    """Start a job without waiting for it.

    A reference is kept until completion: asyncio only holds a weak reference to
    a task, so without this the garbage collector can cancel a long job
    mid-flight, which is a genuinely baffling bug to meet in the wild.
    """
    task = asyncio.create_task(run_job(job_id, work))
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)


_RUNNING: set[asyncio.Task] = set()


def reap_stale_jobs(db) -> int:
    """Fail jobs left "running" by a process that went away.

    Called at startup. Without it a restart mid-generation leaves a row that the
    client polls forever, because nothing is left alive to finish it.
    """
    from app.models.ai import GenerationJob

    cutoff = _now() - timedelta(minutes=STALE_AFTER_MINUTES)
    try:
        stale = (
            db.query(GenerationJob)
            .filter(
                GenerationJob.status.in_(["queued", "running"]),
                GenerationJob.created_at < cutoff,
            )
            .all()
        )
        for job in stale:
            job.status = "failed"
            job.error = "Generation was interrupted. Try again."
            job.finished_at = _now()
        db.commit()
        if stale:
            logger.info("Reaped %d stale generation job(s)", len(stale))
        return len(stale)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not reap stale jobs: %s", exc)
        db.rollback()
        return 0
