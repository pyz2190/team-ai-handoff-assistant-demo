from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def require(condition: bool, code: str, message: str, status: int = 400) -> None:
    if not condition:
        raise DomainError(code, message, status)
