"""Security contracts for the closed semantic-provider boundary."""

from __future__ import annotations

import json

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport

from skillscout.adapters.semantic_provider import (
    DEEPSEEK_MODEL,
    SemanticProvider,
    create_semantic_client,
    request_deepseek_json,
    resolve_semantic_provider,
)
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.models import StrictFrozenModel

CHAT_COMPLETIONS = ("POST", "/chat/completions")
CANARY_KEY = "deepseek-canary-key-do-not-disclose"
CANARY_BASE_URL = "https://api.deepseek.com"


class _Answer(StrictFrozenModel):
    value: str


def _chat_response(
    content: str | None,
    *,
    finish_reason: str = "stop",
    choices: int = 1,
) -> RecordedResponse:
    choice = {
        "index": 0,
        "message": {"role": "assistant", "content": content},
        "finish_reason": finish_reason,
    }
    body = {
        "id": "chatcmpl-deepseek-1",
        "object": "chat.completion",
        "created": 1,
        "model": DEEPSEEK_MODEL,
        "choices": [choice for _ in range(choices)],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
        },
    }
    return RecordedResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(body).encode(),
    )


def test_default_provider_is_openai_and_secret_free() -> None:
    settings = resolve_semantic_provider({})

    assert settings.provider is SemanticProvider.OPENAI
    assert settings.api_key_env == "OPENAI_API_KEY"
    assert settings.base_url is None
    assert settings.extract_model == "gpt-5.6-terra"
    assert "key" not in repr(settings).lower()


def test_deepseek_requires_exact_official_origin_and_fixed_model() -> None:
    settings = resolve_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": f"{CANARY_BASE_URL}/",
        }
    )

    assert settings.provider is SemanticProvider.DEEPSEEK
    assert settings.api_key_env == "DEEPSEEK_API_KEY"
    assert settings.base_url == CANARY_BASE_URL
    assert settings.extract_model == DEEPSEEK_MODEL
    assert settings.generator_model == DEEPSEEK_MODEL
    assert settings.reviewer_model == DEEPSEEK_MODEL
    assert CANARY_BASE_URL not in repr(settings)


@pytest.mark.parametrize(
    "value",
    (
        "",
        "http://api.deepseek.com",
        "https://user@api.deepseek.com",
        "https://api.deepseek.com:443",
        "https://evil.api.deepseek.com",
        "https://127.0.0.1",
        "https://api.deepseek.com/beta",
        "https://api.deepseek.com?x=1",
        "https://api.deepseek.com#x",
    ),
)
def test_deepseek_rejects_noncanonical_endpoints_without_echo(value: str) -> None:
    with pytest.raises(SafeFailure) as failure:
        resolve_semantic_provider(
            {
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": value,
            }
    )

    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE
    if value:
        assert value not in str(failure.value)


def test_unknown_provider_fails_closed_without_echo() -> None:
    rejected = "provider-canary"
    with pytest.raises(SafeFailure) as failure:
        resolve_semantic_provider({"SKILLSCOUT_LLM_PROVIDER": rejected})
    assert failure.value.code is ErrorCode.STAGE_PERMANENT_FAILURE
    assert rejected not in str(failure.value)


def test_deepseek_chat_request_is_one_toolless_strict_json_call() -> None:
    recorded = RecordedTransport({CHAT_COMPLETIONS: _chat_response('{"value":"ok"}')})
    settings = resolve_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": CANARY_BASE_URL,
        }
    )
    client = create_semantic_client(
        settings,
        api_key=CANARY_KEY,
        http_client=httpx.Client(transport=recorded.transport()),
    )

    result = request_deepseek_json(
        client,
        model=DEEPSEEK_MODEL,
        instructions="trusted instructions",
        user_payload="untrusted payload",
        response_model=_Answer,
        max_tokens=123,
    )

    assert result.status == "parsed"
    assert result.parsed == _Answer(value="ok")
    assert recorded.call_count(*CHAT_COMPLETIONS) == 1
    request = recorded.requests[0]
    assert request.url.host == "api.deepseek.com"
    assert request.headers["authorization"] == f"Bearer {CANARY_KEY}"
    body = json.loads(request.content)
    assert body["model"] == DEEPSEEK_MODEL
    assert body["messages"][0]["role"] == "system"
    assert "trusted instructions" in body["messages"][0]["content"]
    assert "_Answer" in body["messages"][0]["content"]
    assert body["messages"][1] == {"role": "user", "content": "untrusted payload"}
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 123
    assert body["stream"] is False
    assert body["thinking"] == {"type": "disabled"}
    assert "tools" not in body
    assert "tool_choice" not in body
    assert CANARY_KEY.encode() not in request.content
    assert CANARY_BASE_URL.encode() not in request.content


@pytest.mark.parametrize(
    ("response", "expected"),
    (
        (_chat_response(None), "schema_invalid"),
        (_chat_response(""), "schema_invalid"),
        (_chat_response('{"value":"ok"}', finish_reason="length"), "incomplete"),
        (_chat_response('{"value":"ok"}', choices=2), "schema_invalid"),
        (_chat_response('{"value":"ok","extra":1}'), "schema_invalid"),
        (_chat_response("not-json"), "schema_invalid"),
    ),
)
def test_deepseek_response_must_be_single_terminal_strict_schema(
    response: RecordedResponse,
    expected: str,
) -> None:
    recorded = RecordedTransport({CHAT_COMPLETIONS: response})
    settings = resolve_semantic_provider(
        {
            "SKILLSCOUT_LLM_PROVIDER": "deepseek",
            "DEEPSEEK_BASE_URL": CANARY_BASE_URL,
        }
    )
    client = create_semantic_client(
        settings,
        api_key=CANARY_KEY,
        http_client=httpx.Client(transport=recorded.transport()),
    )

    result = request_deepseek_json(
        client,
        model=DEEPSEEK_MODEL,
        instructions="trusted",
        user_payload="untrusted",
        response_model=_Answer,
        max_tokens=32,
    )

    assert result.status == expected
    assert result.parsed is None
    assert recorded.call_count(*CHAT_COMPLETIONS) == 1
