"""Closed provider selection and guarded DeepSeek structured transport."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Literal, Mapping, TypeVar

import openai
from pydantic import BaseModel, ValidationError

from skillscout.application.ports import ErrorCode, SafeFailure

OPENAI_MODEL = "gpt-5.6-terra"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_OFFICIAL_BASE_URL = "https://api.deepseek.com"

_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)


class SemanticProvider(str, Enum):
    """The complete provider set admitted by SkillScout."""

    OPENAI = "openai"
    DEEPSEEK = "deepseek"


@dataclass(frozen=True, repr=False)
class SemanticProviderSettings:
    """Non-secret provider identity resolved independently of credentials."""

    provider: SemanticProvider
    api_key_env: str
    extract_model: str
    generator_model: str
    reviewer_model: str
    base_url: str | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        return (
            "SemanticProviderSettings("
            f"provider={self.provider.value!r}, "
            f"extract_model={self.extract_model!r}, "
            f"generator_model={self.generator_model!r}, "
            f"reviewer_model={self.reviewer_model!r})"
        )


@dataclass(frozen=True)
class DeepSeekJSONResult(Generic[_ResponseModel]):
    """One locally decoded, schema-bounded Chat Completions response."""

    status: Literal["parsed", "incomplete", "schema_invalid"]
    parsed: _ResponseModel | None
    request_id: object | None = field(default=None, repr=False)
    model: object | None = field(default=None, repr=False)
    usage: object | None = field(default=None, repr=False)


def resolve_semantic_provider(
    environ: Mapping[str, str] | None = None,
) -> SemanticProviderSettings:
    """Resolve one closed non-secret provider profile without retaining input."""

    source = os.environ if environ is None else environ
    selected = source.get("SKILLSCOUT_LLM_PROVIDER", "openai")
    if selected == SemanticProvider.OPENAI.value:
        return SemanticProviderSettings(
            provider=SemanticProvider.OPENAI,
            api_key_env="OPENAI_API_KEY",
            extract_model=OPENAI_MODEL,
            generator_model=OPENAI_MODEL,
            reviewer_model=OPENAI_MODEL,
        )
    if selected != SemanticProvider.DEEPSEEK.value:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)

    candidate = source.get("DEEPSEEK_BASE_URL")
    normalized = candidate[:-1] if candidate and candidate.endswith("/") else candidate
    if normalized != DEEPSEEK_OFFICIAL_BASE_URL:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    return SemanticProviderSettings(
        provider=SemanticProvider.DEEPSEEK,
        api_key_env="DEEPSEEK_API_KEY",
        extract_model=DEEPSEEK_MODEL,
        generator_model=DEEPSEEK_MODEL,
        reviewer_model=DEEPSEEK_MODEL,
        base_url=DEEPSEEK_OFFICIAL_BASE_URL,
    )


def create_semantic_client(
    settings: SemanticProviderSettings,
    *,
    api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
    http_client: Any = None,
) -> openai.OpenAI:
    """Bind exactly one provider credential to a zero-retry SDK client."""

    if type(settings) is not SemanticProviderSettings:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    source = os.environ if environ is None else environ
    resolved_key = api_key if api_key is not None else source.get(settings.api_key_env)
    if not resolved_key:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    arguments: dict[str, object] = {
        "api_key": resolved_key,
        "http_client": http_client,
        "max_retries": 0,
    }
    if settings.provider is SemanticProvider.DEEPSEEK:
        if settings.base_url != DEEPSEEK_OFFICIAL_BASE_URL:
            raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
        arguments["base_url"] = DEEPSEEK_OFFICIAL_BASE_URL
    return openai.OpenAI(**arguments)


def request_deepseek_json(
    client: openai.OpenAI,
    *,
    model: str,
    instructions: str,
    user_payload: str,
    response_model: type[_ResponseModel],
    max_tokens: int,
) -> DeepSeekJSONResult[_ResponseModel]:
    """Make one no-tools JSON request and strictly validate assistant content."""

    if (
        model != DEEPSEEK_MODEL
        or not instructions
        or type(user_payload) is not str
        or max_tokens < 1
    ):
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    schema = json.dumps(
        response_model.model_json_schema(),
        sort_keys=True,
        separators=(",", ":"),
    )
    trusted = (
        f"{instructions}\n\n"
        "Return one JSON object only. It must conform exactly to this trusted "
        f"{response_model.__name__} JSON Schema:\n{schema}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": trusted},
                {"role": "user", "content": user_payload},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except (
        openai.RateLimitError,
        openai.InternalServerError,
        openai.APITimeoutError,
        openai.APIConnectionError,
    ):
        raise SafeFailure(ErrorCode.STAGE_TRANSIENT_FAILURE) from None
    except openai.APIError:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE) from None

    choices = response.choices
    if len(choices) != 1:
        return _closed_deepseek_result("schema_invalid", response)
    choice = choices[0]
    if choice.finish_reason != "stop":
        return _closed_deepseek_result("incomplete", response)
    content = choice.message.content
    if type(content) is not str or not content:
        return _closed_deepseek_result("schema_invalid", response)
    try:
        parsed = response_model.model_validate_json(content, strict=True)
    except ValidationError:
        return _closed_deepseek_result("schema_invalid", response)
    return DeepSeekJSONResult(
        status="parsed",
        parsed=parsed,
        request_id=response.id,
        model=response.model,
        usage=response.usage,
    )


def _closed_deepseek_result(
    status: Literal["incomplete", "schema_invalid"],
    response: object,
) -> DeepSeekJSONResult[Any]:
    return DeepSeekJSONResult(
        status=status,
        parsed=None,
        request_id=getattr(response, "id", None),
        model=getattr(response, "model", None),
        usage=getattr(response, "usage", None),
    )
