"""Local rejection diagnostics expose categories, never rejected content."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticCustomError

from recorded_transport import RecordedResponse, RecordedTransport
from test_local_generation_preview import (
    _local_client,
    _request_with_source_fields,
    _response_draft,
)
from test_openai_generate import (
    CANARY_KEY,
    CHAT_COMPLETIONS,
    _deepseek_client,
    _deepseek_response,
    _request,
)
from skillscout.adapters.semantic_provider import SemanticProviderFailure
from skillscout.domain.generation_diagnostics import rejection_diagnostic


PRIVATE = "PRIVATE_CANARY_DO_NOT_PERSIST"


def _response(case: str) -> RecordedResponse:
    draft = _response_draft(
        approvals=["The source does not specify approval requirements."],
        failure_handling=["The source does not specify failure handling."],
    )
    if case == "schema":
        draft["approvals"] = []
    elif case == "extra":
        draft[PRIVATE] = PRIVATE
    elif case == "nested":
        draft["references"] = [
            {
                "schema_version": "generated-reference-v1",
                "name": "details",
                "title": "Details",
                "body": "Text",
                PRIVATE: PRIVATE,
            }
        ]
    elif case == "source":
        draft["approvals"] = [PRIVATE]
        draft["failure_handling"] = [PRIVATE]
    content = "{" + PRIVATE if case == "json" else json.dumps(draft)
    if case == "empty":
        content = ""
    response = _deepseek_response(content)
    if case == "choices":
        body = json.loads(response.body)
        body["choices"] *= 2
        return RecordedResponse(
            status=200, headers=response.headers, body=json.dumps(body).encode()
        )
    return response


@pytest.mark.parametrize(
    ("case", "reason", "findings"),
    [
        ("choices", "response_shape", []),
        ("empty", "empty_content", []),
        ("json", "json_invalid", [{"field": "document", "code": "json_invalid"}]),
        ("schema", "schema_invalid", [{"field": "approvals", "code": "too_short"}]),
        ("extra", "schema_invalid", [{"field": "document", "code": "extra_forbidden"}]),
        ("nested", "schema_invalid", [{"field": "references", "code": "extra_forbidden"}]),
        (
            "source",
            "source_contract",
            [
                {"field": "approvals", "code": "source_unspecified_mismatch"},
                {"field": "failure_handling", "code": "source_unspecified_mismatch"},
            ],
        ),
    ],
)
def test_local_rejection_classifies_without_echoing_data(case, reason, findings):
    recorded = RecordedTransport({CHAT_COMPLETIONS: _response(case)})
    with _local_client(recorded, deepseek=True) as client:
        result = client.generate(
            request=_request_with_source_fields(approvals=(), failure_modes=())
        )
        assert result.status == "schema_invalid" and result.draft is None
        assert client.last_diagnostic == {
            "schema_version": "local-generation-diagnostic-v1",
            "reason": reason,
            "findings": findings,
            "truncated": False,
        }
        safe = json.dumps(client.last_diagnostic) + result.model_dump_json()
        assert PRIVATE not in safe and CANARY_KEY not in safe
    assert len(recorded.requests) == 1


def test_default_generator_does_not_collect_diagnostics():
    recorded = RecordedTransport({CHAT_COMPLETIONS: _response("json")})
    with _deepseek_client(recorded) as client:
        result = client.generate(request=_request())
        assert result.status == "schema_invalid"
        assert client.last_diagnostic is None


def test_success_clears_prior_diagnostic():
    recorded = RecordedTransport({CHAT_COMPLETIONS: _response("json")})
    with _local_client(recorded, deepseek=True) as client:
        request = _request_with_source_fields(approvals=(), failure_modes=())
        assert client.generate(request=request).status == "schema_invalid"
        assert client.last_diagnostic is not None
        recorded._routes[CHAT_COMPLETIONS] = _response("valid")
        assert client.generate(request=request).status == "parsed"
        assert client.last_diagnostic is None
    assert len(recorded.requests) == 2


def test_unknown_outcome_clears_prior_diagnostic_without_retry():
    recorded = RecordedTransport({CHAT_COMPLETIONS: _response("json")})
    with _local_client(recorded, deepseek=True) as client:
        request = _request_with_source_fields(approvals=(), failure_modes=())
        assert client.generate(request=request).status == "schema_invalid"
        body = json.loads(_response("valid").body)
        body["model"] = PRIVATE
        recorded._routes[CHAT_COMPLETIONS] = RecordedResponse(
            status=200,
            headers={"content-type": "application/json"},
            body=json.dumps(body).encode(),
        )
        with pytest.raises(SemanticProviderFailure):
            client.generate(request=request)
        assert client.last_diagnostic is None
    assert len(recorded.requests) == 2


@pytest.mark.parametrize("deepseek", [True, False])
def test_malformed_telemetry_never_leaves_a_decided_rejection_diagnostic(deepseek):
    from test_local_generation_preview import _openai_response
    from test_openai_generate import RESPONSES

    if deepseek:
        response = _response("json")
        route = CHAT_COMPLETIONS
    else:
        response = _openai_response(_response_draft())
        route = RESPONSES
    body = json.loads(response.body)
    if not deepseek:
        body["output"] = []
    body["usage"]["total_tokens"] = -1
    recorded = RecordedTransport(
        {
            route: RecordedResponse(
                status=200,
                headers=response.headers,
                body=json.dumps(body).encode(),
            )
        }
    )
    with _local_client(recorded, deepseek=deepseek) as client:
        with pytest.raises(SemanticProviderFailure, match="semantic_provider_outcome_unknown"):
            client.generate(request=_request())
        assert client.last_diagnostic is None
    assert len(recorded.requests) == 1


def test_diagnostic_bounds_deduplicates_and_omits_unknown_error_context():
    fields = (
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
    )
    lines = [
        {"type": code, "loc": (field, PRIVATE), "input": PRIVATE}
        for field in fields
        for code in ("missing", "string_type")
    ]
    lines.extend(
        [
            {
                "type": PydanticCustomError(PRIVATE, PRIVATE, {PRIVATE: PRIVATE}),
                "loc": (PRIVATE,),
                "input": PRIVATE,
            },
            lines[0],
        ]
    )
    error = ValidationError.from_exception_data(PRIVATE, lines)
    diagnostic = rejection_diagnostic("schema_invalid", error=error)
    assert diagnostic["truncated"] is True
    assert len(diagnostic["findings"]) == 16
    assert {"field": "document", "code": "invalid_value"} in diagnostic["findings"]
    assert len({(item["field"], item["code"]) for item in diagnostic["findings"]}) == 16
    assert PRIVATE not in json.dumps(diagnostic)


def test_openai_source_constraint_and_parse_failures_have_safe_diagnostics():
    from test_local_generation_preview import _openai_response
    from test_openai_generate import RESPONSES

    recorded = RecordedTransport(
        {RESPONSES: _openai_response(_response_draft(approvals=[PRIVATE]))}
    )
    with _local_client(recorded, deepseek=False) as client:
        result = client.generate(
            request=_request_with_source_fields(approvals=(), failure_modes=("Stop.",))
        )
        assert result.status == "schema_invalid" and result.draft is None
        assert client.last_diagnostic["reason"] == "source_contract"
        assert client.last_diagnostic["findings"] == [
            {"field": "approvals", "code": "source_unspecified_mismatch"},
        ]
        recorded._routes[RESPONSES] = _openai_response(_response_draft(approvals=[]))
        assert client.generate(request=_request()).status == "schema_invalid"
        assert client.last_diagnostic["reason"] == "schema_invalid"
        assert PRIVATE not in json.dumps(client.last_diagnostic)


def test_openai_missing_parsed_output_is_not_misreported_as_source_failure():
    from test_local_generation_preview import _openai_response
    from test_openai_generate import RESPONSES

    response = _openai_response(_response_draft())
    body = json.loads(response.body)
    body["output"] = []
    recorded = RecordedTransport(
        {
            RESPONSES: RecordedResponse(
                status=200,
                headers=response.headers,
                body=json.dumps(body).encode(),
            )
        }
    )
    with _local_client(recorded, deepseek=False) as client:
        result = client.generate(request=_request())
        assert result.status == "schema_invalid"
        assert client.last_diagnostic == {
            "schema_version": "local-generation-diagnostic-v1",
            "reason": "missing_parsed_output",
            "findings": [],
            "truncated": False,
        }
