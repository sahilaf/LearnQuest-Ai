"""Pydantic schemas for Admin endpoints.

OWNER: Member 3. See plan.md §8.3.
"""

from pydantic import BaseModel, Field


class AdminOverviewResponse(BaseModel):
    users: int = Field(default=0, description="Total registered users")
    courses: int = Field(default=0, description="Total courses in system")
    enrollments: int = Field(default=0, description="Total enrollments")
    active_today: int = Field(default=0, description="Users active today")
