from enum import StrEnum


class WorkProgress(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class ReviewState(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    NEEDS_REVIEW = "needs_review"


class RequestStatus(StrEnum):
    PENDING = "pending"
    NEEDS_INFO = "needs_info"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    EXPIRED = "expired"


class MaterialKind(StrEnum):
    TEXT = "text"
    LINK = "link"


class GenerationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class EventStatus(StrEnum):
    PROPOSED = "proposed"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    NOT_EXECUTED = "not_executed"
    UNKNOWN = "unknown"


class EventLifecycle(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    REOPENED = "reopened"


class EventSource(StrEnum):
    USER = "user"
    SYSTEM = "system"
    GENERATOR = "generator"
    EVALUATION = "evaluation"
    MIGRATION = "migration"


class EvidenceState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    MISMATCH = "mismatch"
    UNAUTHORIZED = "unauthorized"
