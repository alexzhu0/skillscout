"""Wave-0 RED contract for the exact-state protected publication handoff."""

from __future__ import annotations

import importlib
import inspect

import pytest


HANDOFF_XFAIL = pytest.mark.xfail(
    strict=True,
    reason="phase5-wave0-protected-handoff-missing",
)
DIGEST = "sha256:" + ("a" * 64)
STATE_SHA = "b" * 40


class _Probe:
    def __init__(self, name: str, calls: list[str], result: object = None) -> None:
        self.name = name
        self.calls = calls
        self.result = result

    def __call__(self, *_args: object, **_kwargs: object) -> object:
        self.calls.append(self.name)
        return self.result


def _bootstrap():
    return importlib.import_module("skillscout.bootstrap")


@HANDOFF_XFAIL
def test_protected_entrypoint_signature_keeps_authority_dependencies_explicit() -> None:
    function = getattr(_bootstrap(), "run_protected_discovery_publication")
    parameters = set(inspect.signature(function).parameters)
    assert {
        "handoff",
        "state_reader",
        "admission_deriver",
        "catalog_token_factory",
        "publication_factory",
    } <= parameters


@HANDOFF_XFAIL
def test_exact_state_reread_and_all_admissions_precede_token_and_publisher() -> None:
    module = _bootstrap()
    calls: list[str] = []
    admission = object()
    application = type(
        "PublicationProbe",
        (),
        {"run": lambda self, _admission: calls.append("publication_run")},
    )()
    handoff = {
        "state_commit_sha": STATE_SHA,
        "state_root_digest": DIGEST,
        "eligible_candidates": (
            {
                "locator": "state/objects/sha256/aa/" + ("a" * 64) + ".json",
                "authority_digest": DIGEST,
            },
        ),
    }
    module.run_protected_discovery_publication(
        handoff=handoff,
        state_reader=_Probe("state_reread", calls, object()),
        admission_deriver=_Probe("admission", calls, (admission,)),
        catalog_token_factory=_Probe("token", calls, "fixture-token"),
        publication_factory=_Probe("publication_construct", calls, application),
    )
    assert calls == [
        "state_reread",
        "admission",
        "token",
        "publication_construct",
        "publication_run",
    ]


@pytest.mark.parametrize(
    "mutation",
    (
        "stale_state_sha",
        "swapped_root_digest",
        "forged_locator",
        "extra_locator",
        "authority_mismatch",
        "admission_rejected",
    ),
)
@HANDOFF_XFAIL
def test_handoff_mutations_fail_before_token_or_publisher(mutation: str) -> None:
    module = _bootstrap()
    runner = getattr(module, "run_protected_handoff_scenario")
    calls: list[str] = []
    with pytest.raises(Exception):
        runner(
            mutation=mutation,
            state_commit_sha=STATE_SHA,
            state_root_digest=DIGEST,
            token_factory=_Probe("token", calls, "fixture-token"),
            publication_factory=_Probe("publication_construct", calls, object()),
        )
    assert calls == []
