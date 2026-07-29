"""Closed provider selection and guarded DeepSeek structured transport."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any, Final, Generic, Literal, Mapping, TypeVar

from pydantic import BaseModel, ValidationError

from skillscout.application.ports import ErrorCode, SafeFailure

OPENAI_MODEL = "gpt-5.6-terra"
DEEPSEEK_FLASH_MODEL = "deepseek-v4-flash"
DEEPSEEK_PRO_MODEL = "deepseek-v4-pro"
# Historical public name retained for existing all-Flash evidence and callers.
DEEPSEEK_MODEL = DEEPSEEK_FLASH_MODEL
DEEPSEEK_OFFICIAL_BASE_URL = "https://api.deepseek.com"

_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,256}$")


class SemanticTransportDisposition(str, Enum):
    """Closed retry authority for one semantic provider invocation."""

    CONFIRMED_RETRYABLE = "confirmed_retryable"
    SEMANTIC_OUTCOME_UNKNOWN = "semantic_outcome_unknown"
    PERMANENT = "permanent"
    DECIDED = "decided"


class SemanticProviderFailure(Exception):
    """Sanitized provider failure that never retains the originating exception."""

    __slots__ = ("code", "disposition", "request_id")

    def __init__(
        self,
        *,
        disposition: SemanticTransportDisposition,
        code: Literal[
            "semantic_rate_limited",
            "semantic_provider_outcome_unknown",
            "semantic_request_rejected",
        ],
        request_id: str | None = None,
    ) -> None:
        if type(disposition) is not SemanticTransportDisposition:
            raise TypeError("invalid semantic transport disposition")
        expected_codes = {
            SemanticTransportDisposition.CONFIRMED_RETRYABLE: {"semantic_rate_limited"},
            SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN: {
                "semantic_provider_outcome_unknown"
            },
            SemanticTransportDisposition.PERMANENT: {"semantic_request_rejected"},
        }
        if (
            disposition is SemanticTransportDisposition.DECIDED
            or code not in expected_codes[disposition]
            or (
                request_id is not None
                and (type(request_id) is not str or _SAFE_REQUEST_ID.fullmatch(request_id) is None)
            )
        ):
            raise TypeError("invalid semantic provider failure")
        self.disposition = disposition
        self.code = code
        self.request_id = request_id
        super().__init__(code)

    def __repr__(self) -> str:
        return (
            "SemanticProviderFailure("
            f"disposition={self.disposition.value!r}, "
            f"code={self.code!r}, "
            f"request_id={self.request_id!r})"
        )


def classify_semantic_provider_failure(
    error: BaseException,
    *,
    sdk: Any,
) -> SemanticProviderFailure:
    """Classify typed SDK evidence, defaulting every ambiguity to unknown."""

    request_id = _safe_provider_request_id(error)
    if isinstance(error, sdk.RateLimitError):
        return SemanticProviderFailure(
            disposition=SemanticTransportDisposition.CONFIRMED_RETRYABLE,
            code="semantic_rate_limited",
            request_id=request_id,
        )
    if isinstance(error, (sdk.APITimeoutError, sdk.APIConnectionError)):
        return SemanticProviderFailure(
            disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
            code="semantic_provider_outcome_unknown",
            request_id=request_id,
        )
    if isinstance(error, sdk.APIStatusError):
        status_code = getattr(error, "status_code", None)
        if type(status_code) is int and 400 <= status_code < 500:
            if status_code == 408:
                return SemanticProviderFailure(
                    disposition=(SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN),
                    code="semantic_provider_outcome_unknown",
                    request_id=request_id,
                )
            return SemanticProviderFailure(
                disposition=SemanticTransportDisposition.PERMANENT,
                code="semantic_request_rejected",
                request_id=request_id,
            )
    return SemanticProviderFailure(
        disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
        code="semantic_provider_outcome_unknown",
        request_id=request_id,
    )


def _safe_provider_request_id(error: BaseException) -> str | None:
    candidate = getattr(error, "request_id", None)
    if type(candidate) is not str or _SAFE_REQUEST_ID.fullmatch(candidate) is None:
        return None
    return candidate


class SemanticProvider(str, Enum):
    """The complete provider set admitted by SkillScout."""

    OPENAI = "openai"
    DEEPSEEK = "deepseek"


class SemanticStage(StrEnum):
    """The complete set of semantic stages admitted to provider transport."""

    EXTRACTION = "extraction"
    GENERATION = "generation"
    REVIEW = "review"


DEEPSEEK_MODEL_BY_STAGE: Final[Mapping[SemanticStage, str]] = MappingProxyType(
    {
        SemanticStage.EXTRACTION: DEEPSEEK_FLASH_MODEL,
        SemanticStage.GENERATION: DEEPSEEK_FLASH_MODEL,
        SemanticStage.REVIEW: DEEPSEEK_PRO_MODEL,
    }
)


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
        extract_model=DEEPSEEK_MODEL_BY_STAGE[SemanticStage.EXTRACTION],
        generator_model=DEEPSEEK_MODEL_BY_STAGE[SemanticStage.GENERATION],
        reviewer_model=DEEPSEEK_MODEL_BY_STAGE[SemanticStage.REVIEW],
        base_url=DEEPSEEK_OFFICIAL_BASE_URL,
    )


def _validate_semantic_provider_settings(
    settings: SemanticProviderSettings,
) -> None:
    if type(settings) is not SemanticProviderSettings:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)
    if settings.provider is SemanticProvider.OPENAI:
        valid = (
            settings.api_key_env == "OPENAI_API_KEY"
            and settings.extract_model == OPENAI_MODEL
            and settings.generator_model == OPENAI_MODEL
            and settings.reviewer_model == OPENAI_MODEL
            and settings.base_url is None
        )
    elif settings.provider is SemanticProvider.DEEPSEEK:
        valid = (
            settings.api_key_env == "DEEPSEEK_API_KEY"
            and settings.extract_model == DEEPSEEK_MODEL_BY_STAGE[SemanticStage.EXTRACTION]
            and settings.generator_model == DEEPSEEK_MODEL_BY_STAGE[SemanticStage.GENERATION]
            and settings.reviewer_model == DEEPSEEK_MODEL_BY_STAGE[SemanticStage.REVIEW]
            and settings.base_url == DEEPSEEK_OFFICIAL_BASE_URL
        )
    else:
        valid = False
    if not valid:
        raise SafeFailure(ErrorCode.STAGE_PERMANENT_FAILURE)


def create_semantic_client(
    settings: SemanticProviderSettings,
    *,
    sdk: Any,
    api_key: str | None = None,
    environ: Mapping[str, str] | None = None,
    http_client: Any = None,
) -> Any:
    """Bind exactly one provider credential to a zero-retry SDK client."""

    _validate_semantic_provider_settings(settings)
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
        arguments["base_url"] = DEEPSEEK_OFFICIAL_BASE_URL
    return sdk.OpenAI(**arguments)


def request_deepseek_json(
    client: Any,
    *,
    sdk: Any,
    stage: SemanticStage,
    model: str,
    instructions: str,
    user_payload: str,
    response_model: type[_ResponseModel],
    max_tokens: int,
) -> DeepSeekJSONResult[_ResponseModel]:
    """Make one no-tools JSON request and strictly validate assistant content."""

    if (
        type(stage) is not SemanticStage
        or model != DEEPSEEK_MODEL_BY_STAGE[stage]
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
    except sdk.APIError as error:
        raise classify_semantic_provider_failure(error, sdk=sdk) from None

    if getattr(response, "model", None) != model:
        raise SemanticProviderFailure(
            disposition=SemanticTransportDisposition.SEMANTIC_OUTCOME_UNKNOWN,
            code="semantic_provider_outcome_unknown",
        )
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
