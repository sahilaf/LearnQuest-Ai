"""Pydantic request/response models.

Split by domain, mirroring models/. Standard error shape (plan.md 4.2):
    {"detail": "Human readable message", "code": "QUIZ_NOT_FOUND"}
Standard list shape:
    {"items": [...], "total": 137, "page": 1, "page_size": 20}
"""
