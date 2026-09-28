"""Closed local source-faithful generation profile contracts."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from recorded_transport import RecordedResponse, RecordedTransport, recorded_openai_generator_fixture

import skillscout.adapters.state as state_module
from skillscout.adapters.openai_generate import (
    GENERATOR_INSTRUCTIONS_V1,
    GENERATOR_PROMPT_VERSION,
    GenerationRequestV1,
    OpenAIGenerationClient,
)
from skillscout.adapters.semantic_provider import DEEPSEEK_MODEL, resolve_semantic_provider
from skillscout.adapters.state import SQLiteStateStore
from skillscout.application.phase3 import (
    PhaseThreeApplication,
    PhaseThreeDependencies,
    PhaseThreeRuntimeProfile,
    _execution_authority,
)
from skillscout.application.ports import ErrorCode, SafeFailure
from skillscout.domain.candidate_authority import workflow_spec_authority
from skillscout.domain.canonical import canonical_json_bytes
from skillscout.domain.models import TokenUsage
from skillscout.domain.publication import admit_phase3_candidate
from skillscout.domain.skill_artifacts import (
    LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION,
    LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION,
    SOURCE_APPROVALS_UNSPECIFIED,
    SOURCE_FAILURE_HANDLING_UNSPECIFIED,
    GeneratedReferenceV1,
    render_skill_package,
)
from skillscout.domain.validation import validate_local_policy, validate_local_structure

from test_openai_generate import CANARY_KEY, CHAT_COMPLETIONS, RESPONSES, _request
from test_phase3_pipeline import (
    _CascadeGenerator,
    _CascadeReviewer,
    _CascadeValidator,
    _CompositionSource,
    _workflow,
    _write_composition_descriptor_for_workflow,
)
from test_skill_generation import _authority, _draft, _rendered_package


DEFAULT_SKILL_MD_B64 = (
    "LS0tCm5hbWU6ICJyZXZpZXctd29ya2Zsb3ctMTIzNGFiY2QiCmRlc2NyaXB0aW9uOiAiUmV2aWV3IGEg"
    "Ym91bmRlZCB3b3JrZmxvdyB1c2luZyBkZXRlcm1pbmlzdGljIGNoZWNrcy4iCmxpY2Vuc2U6ICJNSVQi"
    "Cm1ldGFkYXRhOgogIHNvdXJjZV9yZXBvc2l0b3J5OiAiaHR0cHM6Ly9naXRodWIuY29tL2V4YW1wbGUv"
    "cmVwb3NpdG9yeSIKICBzb3VyY2VfY29tbWl0OiAiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJiYmJi"
    "YmJiYmJiYmJiYiIKLS0tCgojIE92ZXJ2aWV3CgpBcHBseSBhIHJldXNhYmxlIHJldmlldyBwcm9jZXNz"
    "IHRvIHZlcmlmaWVkIHN0cnVjdHVyZWQgaW5wdXRzLgoKIyMgV2hlbiB0byB1c2UKCi0gQSBzdHJ1Y3R1"
    "cmVkIHdvcmtmbG93IHJlcXVpcmVzIGEgbG9jYWwgcmV2aWV3LgoKIyMgSW5wdXRzCgotIEEgdmVyaWZp"
    "ZWQgd29ya2Zsb3cgc3BlY2lmaWNhdGlvbi4KCiMjIFByb2NlZHVyZQoKMS4gQ29sbGVjdCBvbmx5IHRo"
    "ZSBkZWNsYXJlZCBzdHJ1Y3R1cmVkIGlucHV0cy4KMi4gVmFsaWRhdGUgZWFjaCBpbnB1dCBhZ2FpbnN0"
    "IHRoZSBib3VuZGVkIHBvbGljeS4KMy4gUHJvZHVjZSBhIGxvY2FsIHJldmlldyByZXBvcnQgZm9yIGh1"
    "bWFuIGFzc2Vzc21lbnQuCgojIyBPdXRwdXRzCgotIEEgZGV0ZXJtaW5pc3RpYyByZXZpZXcgcmVwb3J0"
    "LgoKIyMgRmFpbHVyZSBoYW5kbGluZwoKLSBTdG9wIHdoZW4gcmVxdWlyZWQgZXZpZGVuY2UgaXMgbWlz"
    "c2luZy4KCiMjIFJlcXVpcmVkIGFwcHJvdmFscwoKLSBSZXF1aXJlIGh1bWFuIGFwcHJvdmFsIGJlZm9y"
    "ZSBwdWJsaWNhdGlvbi4KCiMjIExpbWl0YXRpb25zCgotIFRoaXMgd29ya2Zsb3cgZG9lcyBub3QgZXhl"
    "Y3V0ZSBjYW5kaWRhdGUgY29kZS4K"
)
def _request_with_source_fields(
    *,
    approvals: tuple[str, ...],
    failure_modes: tuple[str, ...],
) -> GenerationRequestV1:
    request = _request()
    workflow = request.workflow_spec_authority.workflow_spec.model_copy(
        update={"required_approvals": approvals, "failure_modes": failure_modes}
    )
    authority = workflow_spec_authority(
        workflow_spec=workflow,
        phase2_extractor_output_hash=(
            request.workflow_spec_authority.phase2_extractor_output_hash
        ),
        phase2_verified_chain_anchor=(
            request.workflow_spec_authority.phase2_verified_chain_anchor
        ),
    )
    return request.model_copy(update={"workflow_spec_authority": authority})


def _response_draft(**changes: object) -> dict[str, object]:
    body = json.loads(recorded_openai_generator_fixture("parsed_success").body)
    draft = json.loads(body["output"][0]["content"][0]["text"])
    draft.update(changes)
    return draft


def _openai_response(draft: dict[str, object]) -> RecordedResponse:
    fixture = recorded_openai_generator_fixture("parsed_success")
    body = json.loads(fixture.body)
    body["output"][0]["content"][0]["text"] = json.dumps(draft)
    return RecordedResponse(
        status=fixture.status,
        headers=fixture.headers,
        body=json.dumps(body).encode(),
    )


def _deepseek_response(draft: dict[str, object]) -> RecordedResponse:
    return RecordedResponse(
        status=200,
        headers={"content-type": "application/json"},
        body=json.dumps(
            {
                "id": "chatcmpl-generator-1",
                "object": "chat.completion",
                "created": 1,
                "model": DEEPSEEK_MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": json.dumps(draft)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 30,
                    "completion_tokens": 12,
                    "total_tokens": 42,
                },
            }
        ).encode(),
    )


def _local_client(
    recorded: RecordedTransport,
    *,
    deepseek: bool,
) -> OpenAIGenerationClient:
    settings = (
        resolve_semantic_provider(
            {
                "SKILLSCOUT_LLM_PROVIDER": "deepseek",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            }
        )
        if deepseek
        else None
    )
    return OpenAIGenerationClient(
        api_key=CANARY_KEY,
        http_client=httpx.Client(transport=recorded.transport()),
        provider_settings=settings,
        prompt_version=LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION,
    )


def test_current_local_request_omits_optional_quotes_without_changing_source_payload():
    draft = _response_draft(
        approvals=[SOURCE_APPROVALS_UNSPECIFIED],
        failure_handling=[SOURCE_FAILURE_HANDLING_UNSPECIFIED], quotes=[],
    )
    recorded = RecordedTransport({CHAT_COMPLETIONS: _deepseek_response(draft)})
    request = _request_with_source_fields(approvals=(), failure_modes=())
    with _local_client(recorded, deepseek=True) as client:
        result = client.generate(request=request)
        assert client.prompt_version == "generator-local-source-faithful-v2"
    body = json.loads(recorded.requests[0].content)
    assert 'Set quotes to an empty array ([]).' in body["messages"][0]["content"]
    assert json.loads(body["messages"][1]["content"]) == request.model_dump(mode="json")
    assert result.status == "parsed" and result.draft.quotes == ()
    assert recorded.call_count(*CHAT_COMPLETIONS) == 1


@pytest.mark.parametrize("version", ("v1", "v2"))
def test_local_versions_remain_paired_and_single_attempt(version):
    from skillscout.domain.skill_artifacts import uses_local_source_faithful_generation

    profile = f"phase3-local-source-faithful-{version}"
    prompt = f"generator-local-source-faithful-{version}"
    assert uses_local_source_faithful_generation(
        phase3_profile_version=profile, generator_prompt_version=prompt,
    )
    bounded = PhaseThreeRuntimeProfile(
        profile_version=profile, max_generator_attempts=1, max_reviewer_attempts=1,
    )
    assert bounded.generator_prompt_version == prompt
    with pytest.raises(ValueError, match="one attempt"):
        PhaseThreeRuntimeProfile(profile_version=profile, max_generator_attempts=2)
    with pytest.raises(ValueError):
        uses_local_source_faithful_generation(
            phase3_profile_version=profile,
            generator_prompt_version="generator-local-source-faithful-v2" if version == "v1"
            else "generator-local-source-faithful-v1",
        )


@pytest.mark.parametrize("deepseek", (False, True), ids=("openai", "deepseek"))
@pytest.mark.parametrize(
    ("missing_field", "draft_changes"),
    (
        ("approvals", {"approvals": ["A maintainer must approve every output."]}),
        (
            "failure_modes",
            {"failure_handling": ["Retry failures after changing the source."]},
        ),
    ),
)
def test_local_client_rejects_invented_absent_source_fields_with_telemetry(
    deepseek: bool,
    missing_field: str,
    draft_changes: dict[str, object],
) -> None:
    request = _request_with_source_fields(
        approvals=() if missing_field == "approvals" else ("Source approval.",),
        failure_modes=() if missing_field == "failure_modes" else ("Source failure.",),
    )
    draft = _response_draft(**draft_changes)
    route = CHAT_COMPLETIONS if deepseek else RESPONSES
    response = _deepseek_response(draft) if deepseek else _openai_response(draft)
    recorded = RecordedTransport({route: response})

    client = _local_client(recorded, deepseek=deepseek)
    result = client.generate(request=request)

    assert result.status == "schema_invalid"
    assert result.draft is None
    assert result.usage is not None
    assert result.usage.total_tokens == (42 if deepseek else 900)
    assert result.request_id == (
        "chatcmpl-generator-1" if deepseek else "resp_gen_0001"
    )
    assert client.prompt_version == LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION
    assert recorded.call_count(*route) == 1
    body = json.loads(recorded.requests[0].content)
    developer = (
        body["messages"][0]["content"]
        if deepseek
        else body["input"][0]["content"]
    )
    user = (
        body["messages"][1]["content"]
        if deepseek
        else body["input"][1]["content"]
    )
    assert developer.startswith(LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION)
    assert request.workflow_spec_authority.workflow_spec.evidence[0].excerpt in user
    assert request.workflow_spec_authority.workflow_spec.evidence[0].excerpt not in developer


@pytest.mark.parametrize(
    ("approvals", "failure_modes", "draft_changes"),
    (
        (
            (),
            (),
            {
                "approvals": [SOURCE_APPROVALS_UNSPECIFIED],
                "failure_handling": [SOURCE_FAILURE_HANDLING_UNSPECIFIED],
            },
        ),
        (
            ("Source approval is required.",),
            ("Source failure rule.",),
            {
                "approvals": ["Paraphrased source approval."],
                "failure_handling": ["Paraphrased source failure rule."],
            },
        ),
    ),
)
def test_local_client_accepts_exact_sentinels_and_nonempty_source_semantics(
    approvals: tuple[str, ...],
    failure_modes: tuple[str, ...],
    draft_changes: dict[str, object],
) -> None:
    recorded = RecordedTransport(
        {RESPONSES: _openai_response(_response_draft(**draft_changes))}
    )

    result = _local_client(recorded, deepseek=False).generate(
        request=_request_with_source_fields(
            approvals=approvals,
            failure_modes=failure_modes,
        )
    )

    assert result.status == "parsed"
    assert result.draft is not None
    assert recorded.call_count(*RESPONSES) == 1


def test_default_prompt_and_rendered_bytes_are_literal_baseline_compatible() -> None:
    package = _rendered_package()
    skill_text = next(file.content for file in package.files if file.path == "SKILL.md")

    assert hashlib.sha256(GENERATOR_INSTRUCTIONS_V1.encode()).hexdigest() == (
        "1f1508c04f7c484a48465808ec5266ffbc02b0be59c3eac98618b65cd59b5bb0"
    )
    assert skill_text == base64.b64decode(DEFAULT_SKILL_MD_B64)
    assert package.generated_artifact_identity.artifact_digest == (
        "sha256:159e742be88c9d2a6ec1457bf8dc5e54c25c1e7cd9a3f89dde1245c9be5b2ee6"
    )
    assert package.package_identity.rendered_manifest_digest == (
        "sha256:e62b99fa7e8d2fb5bd2fee6501e802da4caae0469ac8d5fd50bda140f66b0d5c"
    )


def _local_authority(**changes: object):
    return _authority(
        phase3_profile_version=LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION,
        generator_prompt_version=LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION,
        **changes,
    )


def test_local_renderer_indexes_four_safe_reference_names_and_zero_is_unchanged() -> None:
    references = tuple(
        GeneratedReferenceV1(
            schema_version="generated-reference-v1",
            name=name,
            title=f"[Untrusted title {index}](https://example.invalid)",
            body=f"Bounded reference body {index}.",
        )
        for index, name in enumerate(
            ("formatting-constraints", "inputs", "output-checks", "failure-notes"),
            start=1,
        )
    )
    package = render_skill_package(
        draft=_draft(references=references),
        authority=_local_authority(),
        request_id="local-render-1",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        latency_ms=1,
    )
    skill_text = next(
        file.content.decode() for file in package.files if file.path == "SKILL.md"
    )

    assert "[formatting-constraints](references/formatting-constraints.md)" in skill_text
    assert "Untrusted title" not in skill_text
    assert [skill_text.index(f"[{reference.name}]") for reference in references] == sorted(
        skill_text.index(f"[{reference.name}]") for reference in references
    )
    assert not any(
        finding.code == "structure_orphan_resource"
        for finding in validate_local_structure(package)
    )

    no_references = render_skill_package(
        draft=_draft(references=()),
        authority=_local_authority(),
        request_id="local-render-2",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        latency_ms=1,
    )
    zero_text = next(
        file.content.decode()
        for file in no_references.files
        if file.path == "SKILL.md"
    )
    assert "## References" not in zero_text


@pytest.mark.parametrize(
    ("profile_version", "prompt_version"),
    (
        (LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION, GENERATOR_PROMPT_VERSION),
        ("phase3-profile-v1", LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION),
    ),
)
def test_renderer_rejects_mixed_local_and_default_identity_pairs(
    profile_version: str,
    prompt_version: str,
) -> None:
    with pytest.raises(ValueError, match="profile and prompt disagree"):
        render_skill_package(
            draft=_draft(steps=("Run pip install an-untrusted-package.",)),
            authority=_authority(
                phase3_profile_version=profile_version,
                generator_prompt_version=prompt_version,
            ),
            request_id="mixed-identity",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            latency_ms=1,
        )


def test_local_renderer_does_not_weaken_eighty_character_overcopy_boundary() -> None:
    copied = "z" * 80
    base = _local_authority()
    workflow = base.workflow_spec_authority.workflow_spec
    evidence = workflow.evidence[0].model_copy(update={"excerpt": copied})
    changed_workflow = workflow.model_copy(update={"evidence": (evidence,)})
    changed_workflow_authority = workflow_spec_authority(
        workflow_spec=changed_workflow,
        phase2_extractor_output_hash=(
            base.workflow_spec_authority.phase2_extractor_output_hash
        ),
        phase2_verified_chain_anchor=base.phase2_verified_chain_anchor,
    )
    package = render_skill_package(
        draft=_draft(overview=copied),
        authority=base.model_copy(
            update={"workflow_spec_authority": changed_workflow_authority}
        ),
        request_id="local-overcopy",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        latency_ms=1,
    )

    assert "overcopy_unregistered_source_match" in {
        finding.code for finding in validate_local_policy(package)
    }


def test_local_renderer_never_repairs_unsupported_semantic_fields() -> None:
    base = _local_authority()
    workflow = base.workflow_spec_authority.workflow_spec.model_copy(
        update={"required_approvals": (), "failure_modes": ()}
    )
    changed_workflow_authority = workflow_spec_authority(
        workflow_spec=workflow,
        phase2_extractor_output_hash=(
            base.workflow_spec_authority.phase2_extractor_output_hash
        ),
        phase2_verified_chain_anchor=base.phase2_verified_chain_anchor,
    )
    package = render_skill_package(
        draft=_draft(
            approvals=("Invented approval.",),
            failure_handling=("Invented recovery.",),
        ),
        authority=base.model_copy(
            update={"workflow_spec_authority": changed_workflow_authority}
        ),
        request_id="local-no-repair",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        latency_ms=1,
    )
    skill_text = next(
        file.content.decode() for file in package.files if file.path == "SKILL.md"
    )

    assert "Invented approval." in skill_text
    assert "Invented recovery." in skill_text
    assert SOURCE_APPROVALS_UNSPECIFIED not in skill_text
    assert SOURCE_FAILURE_HANDLING_UNSPECIFIED not in skill_text


def _source_for_authority() -> SimpleNamespace:
    workflow = _workflow()
    return SimpleNamespace(
        descriptor=SimpleNamespace(
            selected_workflow_fingerprint=workflow.fingerprint,
            prior_lineage_binding_digest=None,
        ),
        workflow_spec_authority=workflow_spec_authority(
            workflow_spec=workflow,
            phase2_extractor_output_hash="sha256:" + "3" * 64,
            phase2_verified_chain_anchor="sha256:" + "4" * 64,
        ),
    )


def _local_profile() -> PhaseThreeRuntimeProfile:
    return PhaseThreeRuntimeProfile(
        profile_version=LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION,
        configured_generator_model_id="generator-configured",
        configured_reviewer_model_id="reviewer-configured",
        max_generator_attempts=1,
        max_reviewer_attempts=1,
    )


def test_local_profile_rejects_unbounded_attempt_caps() -> None:
    with pytest.raises(ValueError, match="one attempt"):
        PhaseThreeRuntimeProfile(
            profile_version=LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION,
            max_generator_attempts=3,
            max_reviewer_attempts=1,
        )

    with pytest.raises(ValueError, match="one attempt"):
        PhaseThreeRuntimeProfile(
            profile_version=LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION,
            max_generator_attempts=1,
            max_reviewer_attempts=2,
        )


def test_local_profile_binds_prompt_and_separates_default_completed_identity() -> None:
    source = _source_for_authority()
    default_profile = PhaseThreeRuntimeProfile(
        configured_generator_model_id="generator-configured",
        configured_reviewer_model_id="reviewer-configured",
    )
    default = _execution_authority(source=source, profile=default_profile)
    local = _execution_authority(source=source, profile=_local_profile())

    assert default.generator_prompt_version == GENERATOR_PROMPT_VERSION
    assert local.generator_prompt_version == LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION
    assert local.phase3_profile_version == LOCAL_SOURCE_FAITHFUL_PROFILE_VERSION
    assert local.runtime_profile_digest != default.runtime_profile_digest
    assert local.authority_digest != default.authority_digest


def test_local_profile_requires_exact_prompt_identity_before_generator_dispatch(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    descriptor = _write_composition_descriptor_for_workflow(
        tmp_path,
        workflow=_workflow(),
    )

    class Miss:
        def find_completed_candidate(self, _authority):
            return None

    with pytest.raises(SafeFailure) as raised:
        PhaseThreeApplication(
            source=_CompositionSource(workflow=_workflow()),
            profile=_local_profile(),
            dependencies=PhaseThreeDependencies(
                completed_projector_factory=Miss,
                mutable_state_factory=lambda: SQLiteStateStore(tmp_path / "state.db"),
                generator_factory=lambda: _CascadeGenerator("parsed", calls),
                validator_factory=lambda: pytest.fail("validator must not run"),
                reviewer_factory=lambda: pytest.fail("reviewer must not run"),
                artifact_projector_factory=lambda: pytest.fail("projector must not run"),
            ),
        ).run(descriptor)

    assert raised.value.code is ErrorCode.STAGE_PERMANENT_FAILURE
    assert calls == []


def test_local_generation_rejection_never_reaches_reviewer(tmp_path: Path) -> None:
    calls: list[str] = []
    descriptor = _write_composition_descriptor_for_workflow(
        tmp_path,
        workflow=_workflow(),
    )
    generator = _CascadeGenerator("schema_invalid", calls)
    generator.prompt_version = LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION

    class Miss:
        def find_completed_candidate(self, _authority):
            return None

    result = PhaseThreeApplication(
        source=_CompositionSource(workflow=_workflow()),
        profile=_local_profile(),
        dependencies=PhaseThreeDependencies(
            completed_projector_factory=Miss,
            mutable_state_factory=lambda: SQLiteStateStore(tmp_path / "state.db"),
            generator_factory=lambda: generator,
            validator_factory=lambda: pytest.fail("validator must not run"),
            reviewer_factory=lambda: pytest.fail("reviewer must not run"),
            artifact_projector_factory=lambda: pytest.fail("projector must not run"),
        ),
    ).run(descriptor)

    assert result.outcome == "generator_schema_failure"
    assert calls == ["generator"]


def test_local_completed_result_replays_exactly_but_default_cannot_cross_reuse(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.db"
    descriptor = _write_composition_descriptor_for_workflow(
        tmp_path,
        workflow=_workflow(),
    )
    calls: list[str] = []
    generator = _CascadeGenerator("parsed", calls)
    generator.prompt_version = LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION
    first = PhaseThreeApplication(
        source=_CompositionSource(workflow=_workflow()),
        profile=_local_profile(),
        dependencies=PhaseThreeDependencies(
            completed_projector_factory=lambda: (
                state_module.DescriptorAnchoredCompletedCandidateProjector(state_path)
            ),
            mutable_state_factory=lambda: SQLiteStateStore(state_path),
            generator_factory=lambda: generator,
            validator_factory=lambda: _CascadeValidator(False, calls),
            reviewer_factory=lambda: _CascadeReviewer(
                "eligible_local_candidate", calls
            ),
            artifact_projector_factory=lambda: object(),
            run_id_factory=lambda: "local-completed-replay",
        ),
    ).run(descriptor)
    assert first.outcome == "eligible_local_candidate"
    assert calls == ["generator", "validator", "reviewer"]

    replay = PhaseThreeApplication(
        source=_CompositionSource(workflow=_workflow()),
        profile=_local_profile(),
        dependencies=PhaseThreeDependencies(
            completed_projector_factory=lambda: (
                state_module.DescriptorAnchoredCompletedCandidateProjector(state_path)
            ),
            mutable_state_factory=lambda: pytest.fail("mutable state must not open"),
            generator_factory=lambda: pytest.fail("generator must not open"),
            validator_factory=lambda: pytest.fail("validator must not open"),
            reviewer_factory=lambda: pytest.fail("reviewer must not open"),
            artifact_projector_factory=lambda: pytest.fail("projector must not open"),
        ),
    ).run(descriptor)
    assert replay.completed_projection is not None
    assert replay.authority == first.authority
    assert calls == ["generator", "validator", "reviewer"]

    default_calls: list[str] = []
    crossed = PhaseThreeApplication(
        source=_CompositionSource(workflow=_workflow()),
        profile=PhaseThreeRuntimeProfile(
            configured_generator_model_id="generator-configured",
            configured_reviewer_model_id="reviewer-configured",
        ),
        dependencies=PhaseThreeDependencies(
            completed_projector_factory=lambda: (
                state_module.DescriptorAnchoredCompletedCandidateProjector(state_path)
            ),
            mutable_state_factory=lambda: SQLiteStateStore(state_path),
            generator_factory=lambda: _CascadeGenerator(
                "schema_invalid", default_calls
            ),
            validator_factory=lambda: pytest.fail("validator must not run"),
            reviewer_factory=lambda: pytest.fail("reviewer must not run"),
            artifact_projector_factory=lambda: pytest.fail("projector must not run"),
            run_id_factory=lambda: "default-cross-reuse-denied",
        ),
    ).run(descriptor)
    assert crossed.completed_projection is None
    assert crossed.outcome == "generator_schema_failure"
    assert crossed.authority != first.authority
    assert default_calls == ["generator"]


def test_publication_denies_local_profile_for_otherwise_eligible_ordinary_source(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.db"
    calls: list[str] = []
    generator = _CascadeGenerator("parsed", calls)
    generator.prompt_version = LOCAL_SOURCE_FAITHFUL_PROMPT_VERSION
    result = PhaseThreeApplication(
        source=_CompositionSource(workflow=_workflow()),
        profile=_local_profile(),
        dependencies=PhaseThreeDependencies(
            completed_projector_factory=lambda: (
                state_module.DescriptorAnchoredCompletedCandidateProjector(state_path)
            ),
            mutable_state_factory=lambda: SQLiteStateStore(state_path),
            generator_factory=lambda: generator,
            validator_factory=lambda: _CascadeValidator(False, calls),
            reviewer_factory=lambda: _CascadeReviewer(
                "eligible_local_candidate", calls
            ),
            artifact_projector_factory=lambda: object(),
            run_id_factory=lambda: "local-publication-denial",
        ),
    ).run(
        _write_composition_descriptor_for_workflow(
            tmp_path,
            workflow=_workflow(),
        )
    )
    assert result.outcome == "eligible_local_candidate"
    assert result.terminal_summary is not None
    assert result.artifacts is not None
    terminal_bytes = canonical_json_bytes(result.terminal_summary)
    publication_artifacts = {
        name: result.artifacts[name]
        for name in (
            "qualification_report",
            "rendered_package",
            "package_manifest",
            "validation_report",
            "review_attestation",
        )
    }
    publication_artifacts["terminal_summary"] = terminal_bytes

    with pytest.raises(ValueError, match="local generation"):
        admit_phase3_candidate(
            terminal_summary=result.terminal_summary,
            terminal_summary_bytes=terminal_bytes,
            artifacts=publication_artifacts,
        )
