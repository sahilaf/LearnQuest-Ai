"""The controlled topic vocabulary. OWNER: Member 1.

Why this is a hard constraint and not a suggestion
--------------------------------------------------
`topic_tag` is the join key for everything that makes this project more than a
quiz app: `topic_mastery`, the misconception behind a wrong answer, and the
roadmap that sequences what to study next. All three find each other by tag
and nothing else.

While every tag was typed by a human that was safe. It stops being safe the
moment a model is tagging generated content: asked to label a lesson about
INNER JOIN it will produce `sql.joins`, `dbms.joins`, `databases.inner_join` and
`dbms.sql_joins` across four calls, all meaning the same thing. Each becomes a
separate mastery row. A student's misconception about joins is then recorded
against a tag that nothing else will ever look up again, the map fragments into
singletons, and the whole model of "we are tracking this belief over time"
silently becomes false.

So generated tags are matched against this vocabulary and anything unmatched is
dropped, exactly as `roadmap_planner.validate_steps()` drops steps that name a
lesson which does not exist. Adding a tag is a deliberate act.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

logger = logging.getLogger("learnquest.topics")


def _normalise(tag: str) -> str:
    """Lowercase, trim, collapse separators. Does not invent a namespace."""
    text = re.sub(r"[\s-]+", "_", str(tag or "").strip().lower())
    return re.sub(r"[^a-z0-9._]", "", text)


def active_tags(db: Session) -> list[str]:
    from app.models.ai import Topic

    rows = (
        db.query(Topic.tag)
        .filter(Topic.is_active.is_(True))
        .order_by(Topic.subject, Topic.tag)
        .all()
    )
    return [r[0] for r in rows]


def vocabulary(db: Session) -> list[dict[str, Any]]:
    """The full active vocabulary, for prompts and for the admin UI."""
    from app.models.ai import Topic

    rows = (
        db.query(Topic)
        .filter(Topic.is_active.is_(True))
        .order_by(Topic.subject, Topic.tag)
        .all()
    )
    return [r.to_dict() for r in rows]


def prompt_block(db: Session, subject: str | None = None) -> str:
    """The vocabulary formatted for a prompt: `tag - label`, one per line.

    A model given the list picks from it far more reliably than one told to
    "use a dotted tag", which is the whole reason this is passed in rather than
    described.
    """
    from app.models.ai import Topic

    query = db.query(Topic).filter(Topic.is_active.is_(True))
    if subject:
        query = query.filter(Topic.subject == subject)

    rows = query.order_by(Topic.subject, Topic.tag).all()
    return "\n".join(f"{r.tag} - {r.label}" for r in rows)


def resolve(db: Session, tags: Iterable[str]) -> list[str]:
    """Keep only tags that exist in the vocabulary, normalised and deduped.

    Returns an empty list rather than raising: a lesson with no recognised tag
    is a lesson the mastery model cannot track, and the caller decides whether
    that is worth rejecting. Silently inventing a tag to avoid an empty list
    would be the worst of the available options.
    """
    known = set(active_tags(db))
    out: list[str] = []
    for raw in tags or []:
        tag = _normalise(raw)
        if tag in known and tag not in out:
            out.append(tag)
        elif tag and tag not in known:
            logger.info("Dropped unknown topic tag %r from generated content", raw)
    return out


def is_known(db: Session, tag: str) -> bool:
    return _normalise(tag) in set(active_tags(db))


# --------------------------------------------------------------------------- #
# Growing the vocabulary
# --------------------------------------------------------------------------- #
#
# A fixed list only works while every course is about something already on it.
# Once students upload their own notes - operating systems, biology, anything -
# a closed list forces the worst available outcome: notes about semaphores get
# tagged `dbms.er_model` because that was the nearest thing on the list, and
# every quiz, mastery row and misconception for that lesson is then filed under
# the wrong subject. Measured 2026-09-29 on a real upload: all four OS lessons
# tagged `dbms.er_model`, and "Practice this lesson" produced a DBMS quiz.
#
# So a model may *propose* a topic, and this is the one place a proposal becomes
# a tag. It stays deliberate, just no longer manual:
#
#   - the model sees the whole vocabulary first and is told to reuse a tag that
#     genuinely fits, so it only proposes when nothing does;
#   - a proposal must carry a human-readable label, and its tag must look like
#     `subject.topic` - `sql.joins` with no label is still dropped;
#   - an existing tag with the same label, or the same name up to a plural,
#     wins over the proposal. `os.semaphore` next to `os.semaphores` is exactly
#     the fragmentation the module docstring warns about.

TAG_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}\.[a-z0-9_]{2,60}$")
MAX_NEW_TOPICS_PER_CALL = 8


def _label_key(label: str) -> str:
    return re.sub(r"\W+", " ", str(label or "").lower()).strip()


def _plural_variants(tag: str) -> list[str]:
    """Spellings of `tag` that differ only by a plural ending.

    Candidates rather than a stem: stemming either misses pairs (`cache` /
    `caches`) or merges words that differ (`process` -> `proces`).
    """
    out = [tag + "s", tag + "es"]
    if tag.endswith("es"):
        out.append(tag[:-2])
    if tag.endswith("s"):
        out.append(tag[:-1])
    return out


def register(
    db: Session,
    proposals: Iterable[dict[str, Any]],
    *,
    limit: int = MAX_NEW_TOPICS_PER_CALL,
) -> dict[str, str]:
    """Map each proposed tag to a real one, creating topics only when needed.

    Returns {proposed tag (normalised): tag to use}. A proposal missing from the
    result was rejected, and the caller should treat it as untagged.
    """
    from app.models.ai import Topic

    rows = db.query(Topic).filter(Topic.is_active.is_(True)).all()
    by_tag = {r.tag: r for r in rows}
    by_label = {_label_key(r.label): r.tag for r in rows}

    mapping: dict[str, str] = {}
    created = 0
    for proposal in proposals or []:
        if not isinstance(proposal, dict):
            continue
        tag = _normalise(proposal.get("tag") or "")
        label = str(proposal.get("label") or "").strip()
        if not tag or tag in mapping:
            continue

        if tag in by_tag:
            mapping[tag] = tag
            continue
        existing = by_label.get(_label_key(label)) if label else None
        existing = existing or next((v for v in _plural_variants(tag) if v in by_tag), None)
        if existing:
            mapping[tag] = existing
            continue

        if not label or not TAG_PATTERN.match(tag) or created >= limit:
            logger.info("Rejected topic proposal %r (label %r)", tag, label)
            continue

        subject = _normalise(proposal.get("subject") or "") or tag.split(".")[0]
        topic = Topic(tag=tag, label=label[:200], subject=subject[:100], is_active=True)
        db.add(topic)
        db.flush()
        created += 1
        by_tag[tag] = topic
        by_label[_label_key(label)] = tag
        mapping[tag] = tag
        logger.info("Registered new topic %r - %s", tag, label)

    return mapping


def resolve_or_register(db: Session, tag: str | None, label: str | None, subject: str | None = None) -> str | None:
    """One lesson's tag: an existing one, a newly registered one, or None."""
    if not tag:
        return None
    if label is None or not str(label).strip():
        known = resolve(db, [tag])  # logs the drop when it is one
        return known[0] if known else None
    if is_known(db, tag):
        return _normalise(tag)
    mapping = register(db, [{"tag": tag, "label": label, "subject": subject}])
    return mapping.get(_normalise(tag))
