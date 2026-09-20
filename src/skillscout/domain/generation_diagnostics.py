"""Content-free, non-authoritative local generation rejection categories."""

from __future__ import annotations

from pydantic import ValidationError

_FIELDS = frozenset(
    {
        "schema_version",
        "description",
        "overview",
        "when_to_use",
        "inputs",
        "steps",
        "outputs",
        "failure_handling",
        "approvals",
        "limitations",
        "references",
        "quotes",
    }
)
_CODES = frozenset(
    {
        "json_invalid",
        "missing",
        "extra_forbidden",
        "string_type",
        "string_too_short",
        "string_too_long",
        "string_pattern_mismatch",
        "tuple_type",
        "list_type",
        "too_short",
        "too_long",
        "literal_error",
        "value_error",
        "model_type",
    }
)
_REASONS = frozenset(
    {
        "response_shape",
        "empty_content",
        "json_invalid",
        "schema_invalid",
        "source_contract",
        "missing_parsed_output",
    }
)
_MAX_FINDINGS = 16


def rejection_diagnostic(
    reason: str,
    *,
    error: ValidationError | None = None,
    fields: tuple[str, ...] = (),
) -> dict[str, object]:
    """Retain fixed categories only; never messages, values or arbitrary paths."""
    if reason not in _REASONS:
        raise ValueError("invalid diagnostic reason")
    findings: set[tuple[str, str]] = set()
    if error is not None:
        for item in error.errors(include_input=False, include_context=False, include_url=False):
            location = item["loc"]
            field = location[0] if location else None
            safe_field = field if type(field) is str and field in _FIELDS else "document"
            code = item["type"]
            safe_code = code if code in _CODES else "invalid_value"
            findings.add((safe_field, safe_code))
            if safe_code == "json_invalid":
                reason = "json_invalid"
    if reason == "source_contract":
        findings.update(
            (name, "source_unspecified_mismatch")
            for name in fields
            if name in {"approvals", "failure_handling"}
        )
    return {
        "schema_version": "local-generation-diagnostic-v1",
        "reason": reason,
        "findings": [
            {"field": name, "code": code} for name, code in sorted(findings)[:_MAX_FINDINGS]
        ],
        "truncated": len(findings) > _MAX_FINDINGS,
    }
