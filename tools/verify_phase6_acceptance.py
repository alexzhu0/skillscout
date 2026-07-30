#!/usr/bin/env python3
"""Independent Phase 6 hard-gate registry; live facts start explicitly absent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from dataclasses import dataclass
from tempfile import TemporaryDirectory
from typing import Sequence


SUCCESS = "phase6 hard-gate registry valid"
OFFLINE_SUCCESS = "phase6 offline authorization prerequisite valid"
INCOMPLETE = "phase6 acceptance incomplete"
INVALID = "phase6 acceptance registry invalid"

PLAN_06_06_STATE_COMMIT = "37f8dcbf74c85f2471670373fd03f71d9f155bae"
PLAN_06_06_STATE_ROOT = "sha256:b4167cffc31969854260d4acd58b804f4823a4d25d078ef3b5dc88445b75c2e5"
PLAN_06_06_WORKFLOW_SHA256 = (
    "sha256:7eca32de7c0468d18c180ebecf567d7239412e54c2776e43621930b894570f63"
)
PLAN_06_06_SOURCE_COMMIT = "a3c41cf8501bec435a646f140f52acedf1c5f312"
PLAN_06_06_HOSTED_RUN_ID = 30_519_607_061
PLAN_06_06_RUN_ATTEMPT = 1
PLAN_06_06_ACCEPTANCE_RUN_ID = "phase6-offline-30519607061-1"
PLAN_06_06_HOSTED_DIGEST = "sha256:cc6f4802e74ec07450958224235b8f0baa8748e74f64b5a1f67c3484998b500a"
PLAN_06_06_OFFLINE_DIGEST = (
    "sha256:f37b81258d966c6683fb16d50aee537e35851dfd41f232490f89d7b0dc228e0b"
)
PLAN_06_06_THREE_STORE_PROJECTION = (
    "sha256:c69f87f4fc213daa36faed3151f0ffe7f99da243363e197db8e59cfb2640b69c"
)


@dataclass(frozen=True)
class HardGate:
    identifier: str
    blocking: bool = True


HARD_GATE_REGISTRY = tuple(
    HardGate(identifier)
    for identifier in (
        "benchmark_human_lock",
        "five_fixed_sha_repositories",
        "controlled_scenario_coverage",
        "hosted_kernel_isolation",
        "synthetic_secret_absence",
        "no_untrusted_execution",
        "closed_provider_policy",
        "license_custody",
        "provenance_custody",
        "evidence_integrity",
        "identical_replay_zero_effects",
        "changed_source_same_draft_update",
        "fresh_gate_b4_binding",
        "permission_causal_denials",
        "open_value_draft",
        "exact_head_human_review",
        "probe_cleanup_attestation",
        "report_rebuild",
        "all_44_requirements",
    )
)


class OfflineStateError(RuntimeError):
    """Fail-closed local verification error with no state or credential detail."""


@dataclass(frozen=True)
class OfflineStateVerification:
    """Sanitized exact identities admitted by the Plan 06-07 checkpoint."""

    state_commit_sha: str
    state_root_digest: str
    acceptance_run_id: str
    workflow_sha256: str
    source_commit_sha: str
    hosted_run_id: int
    run_attempt: int
    isolation_mechanism: str
    hosted_capability_digest: str
    offline_run_digest: str
    three_store_projection_digest: str


def registry_is_exact() -> bool:
    identifiers = tuple(gate.identifier for gate in HARD_GATE_REGISTRY)
    return (
        len(identifiers) == 19
        and len(set(identifiers)) == len(identifiers)
        and all(gate.blocking is True for gate in HARD_GATE_REGISTRY)
        and identifiers[0] == "benchmark_human_lock"
        and identifiers[-1] == "all_44_requirements"
    )


def _git(repository_root: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=repository_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise OfflineStateError("local_git_unavailable") from None
    if result.returncode != 0:
        raise OfflineStateError("local_git_object_missing")
    return result.stdout


def _local_state_remote(repository_root: Path, expected_state_commit: str) -> object:
    from skillscout.adapters.state_branch import (
        STATE_REF,
        StateCommitObservation,
        StateRefObservation,
        StateTreeEntry,
    )

    class LocalStateRemote:
        def get_state_ref(self) -> StateRefObservation:
            observed = (
                _git(
                    repository_root,
                    "rev-parse",
                    "--verify",
                    f"{expected_state_commit}^{{commit}}",
                )
                .decode("ascii")
                .strip()
            )
            if observed != expected_state_commit:
                raise OfflineStateError("canonical_state_object_mismatch")
            return StateRefObservation(STATE_REF, observed)

        def get_commit(self, sha: str) -> StateCommitObservation:
            raw = _git(repository_root, "cat-file", "-p", sha)
            try:
                header, message = raw.split(b"\n\n", 1)
                lines = header.splitlines()
                tree_sha = next(
                    line.removeprefix(b"tree ").decode("ascii")
                    for line in lines
                    if line.startswith(b"tree ")
                )
                parents = tuple(
                    line.removeprefix(b"parent ").decode("ascii")
                    for line in lines
                    if line.startswith(b"parent ")
                )
                decoded_message = message.decode("utf-8").removesuffix("\n")
            except (StopIteration, UnicodeDecodeError, ValueError):
                raise OfflineStateError("canonical_state_commit_invalid") from None
            return StateCommitObservation(
                sha=sha,
                tree_sha=tree_sha,
                parents=parents,
                message=decoded_message,
            )

        def get_tree(self, tree_sha: str) -> tuple[StateTreeEntry, ...]:
            raw = _git(
                repository_root,
                "ls-tree",
                "-r",
                "-l",
                "-z",
                tree_sha,
            )
            entries: list[StateTreeEntry] = []
            try:
                for item in raw.split(b"\0"):
                    if not item:
                        continue
                    metadata, path = item.split(b"\t", 1)
                    mode, object_type, sha, size = metadata.split()
                    if object_type != b"blob":
                        raise ValueError
                    entries.append(
                        StateTreeEntry(
                            path=path.decode("utf-8"),
                            sha=sha.decode("ascii"),
                            mode=mode.decode("ascii"),
                            size=int(size),
                        )
                    )
            except (UnicodeDecodeError, ValueError):
                raise OfflineStateError("canonical_state_tree_invalid") from None
            return tuple(entries)

        def get_blob(self, sha: str) -> bytes:
            return _git(repository_root, "cat-file", "blob", sha)

    return LocalStateRemote()


def verify_offline_state(
    repository_root: Path,
    *,
    expected_state_commit: str = PLAN_06_06_STATE_COMMIT,
) -> OfflineStateVerification:
    """Rebuild and compare the exact Plan 06-06 canonical facts without network."""

    from skillscout.adapters.operations_state import (
        OperationsStateStore,
        _parse_bundle_exports,
        restore_three_store_bundle,
    )
    from skillscout.adapters.state_branch import StateBranchStore
    from skillscout.domain.acceptance import (
        HostedIsolationCapabilityV1,
        OfflineAdversarialRunV1,
    )

    if (
        not isinstance(repository_root, Path)
        or expected_state_commit != PLAN_06_06_STATE_COMMIT
    ):
        raise OfflineStateError("canonical_state_identity_invalid")
    root = repository_root.resolve()
    if _git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip() != str(root):
        raise OfflineStateError("canonical_state_identity_invalid")

    try:
        observation = StateBranchStore(_local_state_remote(root, expected_state_commit)).restore()
        if (
            observation.status != "verified"
            or observation.observed_head != expected_state_commit
            or observation.bundle is None
            or observation.bundle.root.root_digest != PLAN_06_06_STATE_ROOT
        ):
            raise OfflineStateError("canonical_state_restore_mismatch")
        bundle = observation.bundle
        _, operations_export, _, original_projection = _parse_bundle_exports(bundle)
        if (
            operations_export.projection.acceptance_hosted_isolation_capability_digests
            != (PLAN_06_06_HOSTED_DIGEST,)
            or operations_export.projection.acceptance_offline_adversarial_run_digests
            != (PLAN_06_06_OFFLINE_DIGEST,)
            or original_projection.projection_digest != PLAN_06_06_THREE_STORE_PROJECTION
        ):
            raise OfflineStateError("canonical_acceptance_projection_mismatch")

        acceptance_facts = tuple(
            fact for fact in operations_export.facts if fact.kind.startswith("acceptance_")
        )
        if tuple(fact.kind for fact in acceptance_facts) != (
            "acceptance_hosted_isolation_capability",
            "acceptance_offline_adversarial_run",
        ):
            raise OfflineStateError("canonical_acceptance_fact_set_mismatch")
        run_ids = set()
        for fact in acceptance_facts:
            payload = json.loads(fact.payload_json)
            columns = payload.get("columns")
            if type(columns) is not dict:
                raise OfflineStateError("canonical_acceptance_fact_invalid")
            run_ids.add(columns.get("acceptance_run_id"))
        if run_ids != {PLAN_06_06_ACCEPTANCE_RUN_ID}:
            raise OfflineStateError("canonical_acceptance_run_mismatch")

        with TemporaryDirectory(prefix="skillscout-phase6-offline-") as temporary:
            # macOS exposes /tmp and /var as symlink aliases.  The state owners
            # intentionally reject symlinked ancestors, so use the canonical
            # private path to the already-created temporary directory.
            temporary_root = Path(temporary).resolve()
            pipeline_path = temporary_root / "pipeline.sqlite3"
            operations_path = temporary_root / "operations.sqlite3"
            publication_path = temporary_root / "publication.sqlite3"
            rebuilt_projection = restore_three_store_bundle(
                bundle,
                pipeline_path=pipeline_path,
                operations_path=operations_path,
                publication_path=publication_path,
            )
            if rebuilt_projection != original_projection:
                raise OfflineStateError("canonical_three_store_rebuild_mismatch")
            store = OperationsStateStore(operations_path)
            try:
                fresh_export = store.export_owned_state()
                snapshot = store.acceptance_snapshot(PLAN_06_06_ACCEPTANCE_RUN_ID)
            finally:
                store.close()
            if fresh_export != operations_export or tuple(
                record.kind for record in snapshot.facts
            ) != (
                "acceptance_hosted_isolation_capability",
                "acceptance_offline_adversarial_run",
            ):
                raise OfflineStateError("canonical_acceptance_rebuild_mismatch")

        hosted_record, offline_record = snapshot.facts
        hosted = hosted_record.fact
        offline = offline_record.fact
        if (
            type(hosted) is not HostedIsolationCapabilityV1
            or type(offline) is not OfflineAdversarialRunV1
            or hosted_record.fact_digest != PLAN_06_06_HOSTED_DIGEST
            or offline_record.fact_digest != PLAN_06_06_OFFLINE_DIGEST
            or hosted.capability_digest != offline.hosted_capability_digest
            or hosted.workflow_sha256 != offline.workflow_sha256
            or hosted.source_commit_sha != offline.source_commit_sha
            or hosted.hosted_run_id != offline.hosted_run_id
            or hosted.run_attempt != offline.run_attempt
            or hosted.isolation_mechanism != offline.isolation_mechanism
            or hosted.workflow_sha256 != PLAN_06_06_WORKFLOW_SHA256
            or hosted.source_commit_sha != PLAN_06_06_SOURCE_COMMIT
            or hosted.hosted_run_id != PLAN_06_06_HOSTED_RUN_ID
            or hosted.run_attempt != PLAN_06_06_RUN_ATTEMPT
        ):
            raise OfflineStateError("canonical_hosted_offline_binding_mismatch")
        return OfflineStateVerification(
            state_commit_sha=expected_state_commit,
            state_root_digest=bundle.root.root_digest,
            acceptance_run_id=PLAN_06_06_ACCEPTANCE_RUN_ID,
            workflow_sha256=hosted.workflow_sha256,
            source_commit_sha=hosted.source_commit_sha,
            hosted_run_id=hosted.hosted_run_id,
            run_attempt=hosted.run_attempt,
            isolation_mechanism=hosted.isolation_mechanism,
            hosted_capability_digest=hosted_record.fact_digest,
            offline_run_digest=offline_record.fact_digest,
            three_store_projection_digest=rebuilt_projection.projection_digest,
        )
    except OfflineStateError:
        raise
    except Exception:
        raise OfflineStateError("canonical_offline_verification_failed") from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--registry-only", action="store_true")
    parser.add_argument("--offline-only", action="store_true")
    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit:
        print(INVALID, file=sys.stderr)
        return 1
    if not registry_is_exact() or (args.registry_only and args.offline_only):
        print(INVALID, file=sys.stderr)
        return 1
    if args.registry_only:
        print(SUCCESS)
        return 0
    if args.offline_only:
        try:
            report = verify_offline_state(Path.cwd())
        except OfflineStateError:
            print(INCOMPLETE, file=sys.stderr)
            return 1
        print(OFFLINE_SUCCESS)
        print(
            json.dumps(
                report.__dict__,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    # Wave 0 must never convert absent hosted/live/human facts into PASS.
    print(INCOMPLETE, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
