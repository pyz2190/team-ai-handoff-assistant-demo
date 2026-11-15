from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectCreate(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    member_ids: list[str] = Field(default_factory=list, max_length=10)


class MembershipUpdate(StrictModel):
    member_id: str
    active: bool


class TaskCreate(StrictModel):
    title: str = Field(min_length=2, max_length=200)
    goal: str = Field(min_length=2, max_length=5000)
    description: str = Field(default="", max_length=10_000)
    acceptance_criteria: str = Field(min_length=2, max_length=5000)
    owner_id: str | None = None
    progress: Literal["not_started", "in_progress", "blocked", "completed"] = "not_started"


class TaskUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    goal: str | None = Field(default=None, min_length=2, max_length=5000)
    description: str | None = Field(default=None, max_length=10_000)
    acceptance_criteria: str | None = Field(default=None, min_length=2, max_length=5000)
    progress: Literal["not_started", "in_progress", "blocked", "completed"] | None = None
    expected_revision: int = Field(ge=1)


class TextMaterialCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    source_note: str = Field(default="", max_length=1000)
    content: str = Field(min_length=1, max_length=1_048_576)


class LinkMaterialCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    source_note: str = Field(default="", max_length=1000)
    url: HttpUrl


class MaterialVersionCreate(StrictModel):
    content: str = Field(min_length=1, max_length=1_048_576)


class PreviewCreate(StrictModel):
    material_version_ids: list[str] = Field(min_length=1, max_length=100)


class GenerateCreate(StrictModel):
    mode: Literal["normal", "error", "timeout"] = "normal"


class CitationInput(StrictModel):
    section: Literal["completed", "decisions", "verification", "open_issues", "next_steps"]
    material_version_id: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=4000)

    @field_validator("end_line")
    @classmethod
    def end_line_valid(cls, value: int, info):
        start = info.data.get("start_line", 1)
        if value < start:
            raise ValueError("end_line must be greater than or equal to start_line")
        return value


class SectionsInput(StrictModel):
    completed: str = Field(default="", max_length=20_000)
    decisions: str = Field(default="", max_length=20_000)
    verification: str = Field(default="", max_length=20_000)
    open_issues: str = Field(default="", max_length=20_000)
    next_steps: str = Field(default="", max_length=20_000)


class DraftCreate(StrictModel):
    sections: SectionsInput
    citations: list[CitationInput] = Field(default_factory=list, max_length=200)


class DraftUpdate(DraftCreate):
    expected_revision: int = Field(ge=1)


class ConfirmDraft(StrictModel):
    expected_revision: int = Field(ge=1)


class RequestCreate(StrictModel):
    confirmed_handoff_id: str
    recipient_id: str


class RequestAction(StrictModel):
    reason: str = Field(min_length=2, max_length=2000)
    expected_revision: int = Field(ge=1)


class AcceptAction(StrictModel):
    expected_revision: int = Field(ge=1)
