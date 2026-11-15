from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Iterable

from .enums import EvidenceState

HASH_ALGORITHM = "sha256-v1"
EVIDENCE_SEVERITY = {
    EvidenceState.CURRENT: 0,
    EvidenceState.STALE: 1,
    EvidenceState.MISSING: 2,
    EvidenceState.MISMATCH: 3,
    EvidenceState.UNAUTHORIZED: 4,
}


def canonicalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(canonicalize_text(value).encode("utf-8")).hexdigest()


def build_quote(content: str, start_line: int, end_line: int) -> str:
    if start_line < 1 or end_line < start_line:
        raise ValueError("invalid line range")
    lines = canonicalize_text(content).split("\n")
    if end_line > len(lines):
        raise ValueError("line range exceeds content")
    return "\n".join(lines[start_line - 1 : end_line])


def quote_fingerprint(
    material_version_id: str,
    section: str,
    start_line: int,
    end_line: int,
    quote: str,
) -> str:
    parts = (
        material_version_id,
        section,
        str(start_line),
        str(end_line),
        canonicalize_text(quote),
    )
    payload = b"".join(
        len(part.encode("utf-8")).to_bytes(8, "big") + part.encode("utf-8") for part in parts
    )
    return hashlib.sha256(payload).hexdigest()


def aggregate_evidence(states: Iterable[EvidenceState]) -> EvidenceState:
    values = list(states)
    if not values:
        return EvidenceState.CURRENT
    return max(values, key=EVIDENCE_SEVERITY.__getitem__)
