"""Document validation and text extraction for uploaded notes.

OWNER: Member 3. See plan.md §6.13, §8.6, and CHECKLIST.md Slot 11.

This module gets text out of a PDF, Markdown or text file and refuses anything
unsafe or unreadable. Turning that text into a course is done by
`services/notes_course.py`, which uses the model to plan and teach lessons.

It used to build the course itself: split on headings or every ~1800 chars,
save each piece verbatim as a lesson, and tag it by keyword overlap - falling
back to the first topic in the vocabulary when nothing matched. Real uploads
came out as unexplained slide text titled after page headers, every lesson
tagged `dbms.er_model` whatever the subject. That code was removed on
2026-09-29 rather than left for someone to wire back in.
"""

from __future__ import annotations

import io
import logging

from fastapi import HTTPException, status

logger = logging.getLogger("learnquest.upload")

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}
MIN_TEXT_CHARS = 50


def validate_file(filename: str, content: bytes, content_type: str | None = None) -> None:
    """Validate file size and extension to prevent malicious uploads or OOM."""
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not be empty.",
            headers={"X-Error-Code": "UPLOAD_EMPTY_FILENAME"},
        )

    # Validate file extension
    lower_name = filename.lower()
    has_valid_ext = any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS)
    if not has_valid_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a PDF (.pdf), Markdown (.md), or text (.txt) file.",
            headers={"X-Error-Code": "UPLOAD_UNSUPPORTED_TYPE"},
        )

    # Check file size limit (10MB)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
            headers={"X-Error-Code": "UPLOAD_TOO_LARGE"},
        )

    if len(content) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty or corrupted.",
            headers={"X-Error-Code": "UPLOAD_EMPTY_FILE"},
        )


def extract_text_from_file(filename: str, content: bytes, content_type: str | None = None) -> str:
    """Extract plain text / markdown from PDF or text-based files."""
    validate_file(filename, content, content_type)
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        try:
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Encrypted or password-protected PDF files are not supported.",
                    headers={"X-Error-Code": "UPLOAD_PDF_ENCRYPTED"},
                )

            pages_text = []
            for idx, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted and extracted.strip():
                    pages_text.append(extracted.strip())

            full_text = "\n\n".join(pages_text).strip()
            if len(full_text) < MIN_TEXT_CHARS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not extract readable text from PDF. The document may be scanned, image-only, or empty.",
                    headers={"X-Error-Code": "UPLOAD_PDF_SCANNED_OR_EMPTY"},
                )
            return full_text
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("PDF extraction failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read PDF document: {exc}",
                headers={"X-Error-Code": "UPLOAD_PDF_READ_ERROR"},
            ) from exc

    # Plain text / Markdown
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not decode text file with UTF-8 or Latin-1 encoding.",
                headers={"X-Error-Code": "UPLOAD_DECODE_ERROR"},
            ) from exc

    clean_text = text.strip()
    if len(clean_text) < MIN_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file contains insufficient text to create a course.",
            headers={"X-Error-Code": "UPLOAD_INSUFFICIENT_TEXT"},
        )
    return clean_text
