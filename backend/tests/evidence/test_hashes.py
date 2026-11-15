import pytest

from app.domain.enums import EvidenceState
from app.domain.evidence import (
    aggregate_evidence,
    build_quote,
    canonicalize_text,
    quote_fingerprint,
    sha256_text,
)


def test_normalization_and_hashes_are_platform_independent():
    decomposed = "Cafe\u0301\r\n第二行"
    composed = "Café\n第二行"
    assert canonicalize_text(decomposed) == composed
    assert sha256_text(decomposed) == sha256_text(composed)
    assert build_quote(decomposed, 2, 2) == "第二行"


def test_quote_hash_binds_location_and_content():
    original = quote_fingerprint("v1", "decisions", 1, 1, "采用 A")
    assert original == quote_fingerprint("v1", "decisions", 1, 1, "采用 A")
    assert original != quote_fingerprint("v1", "next_steps", 1, 1, "采用 A")
    assert original != quote_fingerprint("v1", "decisions", 1, 2, "采用 A")
    with pytest.raises(ValueError):
        build_quote("one", 1, 2)


def test_evidence_severity_is_deterministic():
    assert aggregate_evidence([]) == EvidenceState.CURRENT
    assert (
        aggregate_evidence([EvidenceState.STALE, EvidenceState.MISMATCH]) == EvidenceState.MISMATCH
    )
    assert (
        aggregate_evidence([EvidenceState.MISSING, EvidenceState.UNAUTHORIZED])
        == EvidenceState.UNAUTHORIZED
    )
