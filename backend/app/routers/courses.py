"""Course catalog and enrollment.

OWNER: Member 2 (reads) / Member 3 (writes). See plan.md §7.3.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import database_is_configured, get_db
from app.deps import CurrentUser, OptionalCurrentUser
from app.models.course import Course, Enrollment, Lesson
from app.models.quiz import Quiz
from app.schemas.course import (
    CourseDetailResponse,
    CourseResponse,
    CourseUpdate,
    EnrollmentResponse,
    LessonResponse,
    LessonUpdate,
)
from app.services.events import emit

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=dict[str, Any])
def list_courses(
    search: str | None = None,
    subject: str | None = None,
    difficulty: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: OptionalCurrentUser = None,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Published courses, filterable. Public - no auth required."""
    if not db or not database_is_configured():
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    user_uuid = None
    if user and "id" in user:
        try:
            user_uuid = uuid.UUID(str(user["id"]))
        except Exception:
            user_uuid = None

    if user_uuid:
        query = db.query(Course).filter(
            Course.is_published.is_(True),
            or_(Course.is_private.is_(False), Course.created_by == user_uuid),
        )
    else:
        query = db.query(Course).filter(
            Course.is_published.is_(True), Course.is_private.is_(False)
        )

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Course.title.ilike(search_filter),
                Course.description.ilike(search_filter),
                Course.subject.ilike(search_filter),
            )
        )
    if subject:
        query = query.filter(Course.subject.ilike(subject.strip()))
    if difficulty:
        query = query.filter(Course.difficulty.ilike(difficulty.strip()))

    total = query.count()
    courses = (
        query.order_by(Course.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [CourseResponse.model_validate(c.to_dict()).model_dump() for c in courses]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{slug}", response_model=CourseDetailResponse)
def get_course(
    slug: str,
    user: OptionalCurrentUser = None,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Course detail with its ordered lesson list."""
    if not db or not database_is_configured():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
            headers={"X-Error-Code": "COURSE_NOT_FOUND"},
        )

    # Allow lookup by slug or by UUID
    course = None
    try:
        course_uuid = uuid.UUID(slug)
        course = (
            db.query(Course)
            .options(joinedload(Course.lessons))
            .filter(Course.id == course_uuid)
            .first()
        )
    except ValueError:
        pass

    if not course:
        course = (
            db.query(Course)
            .options(joinedload(Course.lessons))
            .filter(Course.slug == slug)
            .first()
        )

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{slug}' not found.",
            headers={"X-Error-Code": "COURSE_NOT_FOUND"},
        )

    # Security check (plan.md §8.6, CHECKLIST Slot 11): private courses are only accessible by their creator or admin
    if course.is_private:
        user_uuid = None
        if user and "id" in user:
            try:
                user_uuid = uuid.UUID(str(user["id"]))
            except Exception:
                user_uuid = None
        is_admin = bool(user and user.get("role") == "admin")
        is_owner = bool(user_uuid and course.created_by == user_uuid)
        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Course '{slug}' not found.",
                headers={"X-Error-Code": "COURSE_NOT_FOUND"},
            )


    course_dict = course.to_dict(include_lessons=False)
    lesson_ids = [l.id for l in course.lessons]
    quizzes_by_lesson: dict[uuid.UUID, str] = {}
    if lesson_ids:
        quizzes = db.query(Quiz).filter(Quiz.lesson_id.in_(lesson_ids)).all()
        for q in quizzes:
            if q.lesson_id:
                quizzes_by_lesson[q.lesson_id] = str(q.id)

    sorted_lessons = sorted(course.lessons, key=lambda l: l.order_index)
    lessons_out = []
    for l in sorted_lessons:
        l_dict = l.to_dict()
        l_dict["quiz_id"] = quizzes_by_lesson.get(l.id)
        lessons_out.append(l_dict)
    course_dict["lessons"] = lessons_out

    return course_dict


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_course(
    user: CurrentUser,
    payload: dict,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Generate a private course for this learner from a stated goal. (M1)

    Body: {goal, n_lessons=4}

    Returns **202** with a job id, not a course. Generation is an outline call
    plus one call per lesson - measured at ~8s each, so 50-100s in total, well
    past the client's 30s timeout. Poll `GET /api/jobs/{job_id}`; on success its
    `result` carries `{course_id, slug, title, lessons, topics}` and the learner
    is already enrolled.

    The course is auto-published but private to them and marked
    `source="ai_generated"`. Nothing verifies that its content is correct - see
    CHECKLIST Slot 9C.

    Registered here rather than under /api/jobs so it mirrors
    POST /api/quizzes/generate; the asymmetry is that this one is asynchronous
    because it is an order of magnitude slower.
    """
    from app.services.course_planner import generate_course as _generate
    from app.services.jobs import JobLimitReached, create_job, schedule

    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )

    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user."
        ) from err

    goal = str((payload or {}).get("goal") or "").strip()
    if len(goal) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tell us what you want to learn.",
        )

    n_lessons = (payload or {}).get("n_lessons", 4)

    try:
        job = create_job(
            db, user_uuid, "course", {"goal": goal[:400], "n_lessons": n_lessons}
        )
    except JobLimitReached as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(err)
        ) from err

    job_id = job.id

    async def _work(job_db, running_job):
        return await _generate(
            job_db,
            user_id=user_uuid,
            goal=goal,
            n_lessons=n_lessons,
            job_id=running_job.id,
        )

    # The task gets its own session: this request's session closes with the
    # response, a second from now.
    schedule(job_id, _work)

    return {
        "job_id": str(job_id),
        "status": "queued",
        "poll": f"/api/jobs/{job_id}",
    }


@router.post("/{course_id}/enroll")
def enroll(
    course_id: str,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Enroll the current user in a course and emit course.enrolled."""
    if not db or not database_is_configured():
        return {"course_id": course_id, "enrolled": True}

    try:
        c_uuid = uuid.UUID(course_id)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid course ID.",
            headers={"X-Error-Code": "INVALID_COURSE_ID"},
        ) from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found.",
            headers={"X-Error-Code": "COURSE_NOT_FOUND"},
        )

    user_uuid = uuid.UUID(user["id"])
    existing = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user_uuid, Enrollment.course_id == c_uuid)
        .first()
    )

    if existing:
        return {
            "course_id": str(course.id),
            "enrolled": True,
            "already_enrolled": True,
            "enrollment_id": str(existing.id),
        }

    enrollment = Enrollment(user_id=user_uuid, course_id=c_uuid)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    emit(db, user_uuid, "course.enrolled", {"course_id": str(course.id)})

    return {
        "course_id": str(course.id),
        "enrolled": True,
        "already_enrolled": False,
        "enrollment_id": str(enrollment.id),
    }


@router.post(
    "/upload",
    response_model=dict[str, Any],
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_notes_to_course(
    user: CurrentUser,
    file: UploadFile = File(...),
    custom_title: str | None = Query(default=None),
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Upload notes (PDF/MD/TXT) -> a course that teaches them. Returns a job.

    OWNER: Member 3 (extraction) / Member 1 (course pipeline). See plan.md
    §6.13 and `services/notes_course.py`.

    The file is read and validated here, so a bad upload fails at once with a
    400 rather than a minute later. Planning and writing the lessons is one
    model call per lesson plus an outline, so it runs as a generation job:
    poll `GET /api/jobs/{job_id}`; on `succeeded` its `result` carries
    `{course, lessons, topics, course_id, slug, title}`.
    """
    from app.services.jobs import JobLimitReached, create_job, schedule
    from app.services.notes_course import build_course_from_notes
    from app.services.notes_extractor import extract_text_from_file

    if db is None or not database_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured.",
        )

    try:
        user_uuid = uuid.UUID(str(user["id"]))
    except (KeyError, TypeError, ValueError) as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID."
        ) from err

    content = await file.read()
    filename = file.filename or "notes.txt"
    text = extract_text_from_file(filename, content, file.content_type)

    try:
        job = create_job(
            db,
            user_uuid,
            "course",
            {"source": "upload", "filename": filename[:255], "title": (custom_title or "")[:255]},
        )
    except JobLimitReached as err:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(err)
        ) from err

    async def _work(job_db, running_job):
        return await build_course_from_notes(
            job_db,
            user_id=user_uuid,
            text=text,
            filename=filename,
            custom_title=custom_title,
            job_id=running_job.id,
        )

    schedule(job.id, _work)
    return {"job_id": str(job.id), "status": "queued", "poll": f"/api/jobs/{job.id}"}


@router.patch("/{course_id}", response_model=CourseResponse)
def update_user_course(
    course_id: str,
    payload: CourseUpdate,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Allow course creator (or admin) to update their uploaded or owned course title/description."""
    if not db or not database_is_configured():
        return {"id": course_id, "title": payload.title or "Course"}

    try:
        c_uuid = uuid.UUID(course_id)
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid ID format.") from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    is_admin = user.get("role") == "admin"
    is_owner = course.created_by == user_uuid
    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this course.",
        )

    if payload.title is not None:
        course.title = payload.title
    if payload.description is not None:
        course.description = payload.description
    if payload.difficulty is not None:
        course.difficulty = payload.difficulty

    db.commit()
    db.refresh(course)
    return course.to_dict()


@router.patch("/{course_id}/lessons/{lesson_id}", response_model=LessonResponse)
def update_user_lesson(
    course_id: str,
    lesson_id: str,
    payload: LessonUpdate,
    user: CurrentUser,
    db: Session | None = Depends(get_db),
) -> dict[str, Any]:
    """Allow course creator (or admin) to update a lesson title/content in their course."""
    if not db or not database_is_configured():
        return {"id": lesson_id, "title": payload.title or "Lesson"}

    try:
        c_uuid = uuid.UUID(course_id)
        l_uuid = uuid.UUID(lesson_id)
        user_uuid = uuid.UUID(str(user["id"]))
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid ID format.") from err

    course = db.query(Course).filter(Course.id == c_uuid).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    is_admin = user.get("role") == "admin"
    is_owner = course.created_by == user_uuid
    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit lessons in this course.",
        )

    lesson = db.query(Lesson).filter(Lesson.id == l_uuid, Lesson.course_id == c_uuid).first()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in this course.")

    if payload.title is not None:
        lesson.title = payload.title
    if payload.content_md is not None:
        lesson.content_md = payload.content_md
    if payload.order_index is not None:
        lesson.order_index = payload.order_index
    if payload.topic_tags is not None:
        from app.services.topics import resolve

        resolved = resolve(db, payload.topic_tags)
        if not resolved:
            raise HTTPException(
                status_code=422,
                detail="A lesson must have at least one valid topic tag from the vocabulary.",
            )
        lesson.topic_tags = resolved

    db.commit()
    db.refresh(lesson)
    return lesson.to_dict()

