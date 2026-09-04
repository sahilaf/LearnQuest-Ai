"""Pydantic schemas for File Uploads.

OWNER: Member 3. See plan.md §6.13, §8.1.
"""

from typing import Any
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    filename: str
    content_type: str
    file_size_bytes: int
    extracted_text: str = Field(default="", description="Extracted plain text or markdown")
    course_draft: dict[str, Any] | None = Field(
        default=None,
        description="Draft course metadata prepared for M1 splitting and tagging",
    )
