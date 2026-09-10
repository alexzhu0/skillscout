"""Read-only verified query seam over one completed Phase 2 state snapshot."""

from __future__ import annotations

import fcntl
import os
import re
import sqlite3
from pathlib import Path
from typing import Final, Mapping

from pydantic import ValidationError

from skillscout.adapters.localfs import AnchoredDirectory
from skillscout.adapters.state import (
    MAX_STATE_DB_BYTES,
    SQLiteStateStore,
    _complete_stat_facts,
    _read_stable_private_file,
)
from skillscout.application.ports import (
    CandidateSourceUnavailable,
    PhaseTwoCandidateProjection,
)
from skillscout.domain.candidate_authority import CandidateSubjectDescriptorV1
from skillscout.domain.canonical import canonical_json_bytes, sha256_digest
from skillscout.domain.enums import PipelineStage, RunStatus
from skillscout.domain.extraction import WorkflowSpec
from skillscout.domain.filtering import ALLOWED_LICENSE_SPDX
from skillscout.domain.local_preview import (
    LOCAL_README_POLICY_VERSION, LOCAL_README_SCOPE_KEY, LocalReadmeSubject,
)
from skillscout.domain.models import VerifiedRunChain
from skillscout.domain.reading import READER_ORG_MAX_FILE_BYTES, estimate_tokens

PHASE_TWO_PROFILE_VERSION = "phase2-v1"
_PHASE_TWO_STAGES = (
    PipelineStage.SCOUT,
    PipelineStage.FILTER,
    PipelineStage.READER,
    PipelineStage.EXTRACTOR,
)
_VERIFIED_REJECTION_VECTORS: Final = frozenset(
    {
        (
            (PipelineStage.SCOUT, "rejected", None),
            (PipelineStage.FILTER, "skipped", "scout_rejected"),
            (PipelineStage.READER, "skipped", "scout_rejected"),
            (PipelineStage.EXTRACTOR, "skipped", "scout_rejected"),
        ),
        (
            (PipelineStage.SCOUT, "accepted", None),
            (PipelineStage.FILTER, "rejected", None),
            (PipelineStage.READER, "skipped", "filter_rejected"),
            (PipelineStage.EXTRACTOR, "skipped", "filter_rejected"),
        ),
        (
            (PipelineStage.SCOUT, "accepted", None),
            (PipelineStage.FILTER, "accepted", None),
            (PipelineStage.READER, "accepted", None),
            (PipelineStage.EXTRACTOR, "no_workflow", None),
        ),
    }
)
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_PART = re.compile(r"^[A-Za-z0-9_.-]+$")

_READ_ONLY_SQLITE_ACTIONS = frozenset(
    action
    for action in (
        getattr(sqlite3, "SQLITE_SELECT", None),
        getattr(sqlite3, "SQLITE_READ", None),
        getattr(sqlite3, "SQLITE_FUNCTION", None),
        getattr(sqlite3, "SQLITE_RECURSIVE", None),
    )
    if action is not None
)


def _read_only_authorizer(
    action: int,
    _arg1: str | None,
    _arg2: str | None,
    _database: str | None,
    _trigger: str | None,
) -> int:
    return sqlite3.SQLITE_OK if action in _READ_ONLY_SQLITE_ACTIONS else sqlite3.SQLITE_DENY


def _open_read_only_verifier(path: Path) -> SQLiteStateStore:
    """Construct only the existing verifier surface over a query-only connection."""

    resolved = Path(os.path.abspath(os.fspath(path)))
    verifier = SQLiteStateStore.__new__(SQLiteStateStore)
    verifier.path = resolved
    verifier.manifest_root = resolved.with_suffix(".manifests")
    verifier._state_name = AnchoredDirectory.validate_child_name(resolved.name)
    verifier._manifest_name = AnchoredDirectory.validate_child_name(
        verifier.manifest_root.name
    )
    verifier._lock_name = AnchoredDirectory.validate_child_name(
        f".{verifier._state_name}.lock"
    )
    verifier._filesystem_seam = None
    verifier._state_parent = None
    verifier._manifest_anchor = None
    verifier._manifest_stage_anchors = {}
    verifier._lock_descriptor = -1
    verifier._durable_bytes = None
    verifier._poisoned = False
    verifier.connection = None
    try:
        verifier._state_parent = AnchoredDirectory.open(
            resolved.parent,
            create=False,
        )
        state_metadata = verifier._state_parent.stat_child(verifier._state_name)
        lock_metadata = verifier._state_parent.stat_child(verifier._lock_name)
        if state_metadata is None or lock_metadata is None:
            raise ValueError("Phase 2 authority state is incomplete")
        AnchoredDirectory._require_private_regular(state_metadata)
        AnchoredDirectory._require_private_regular(lock_metadata)

        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        verifier._lock_descriptor = os.open(
            verifier._lock_name,
            flags,
            dir_fd=verifier._state_parent.descriptor,
        )
        opened_lock = os.fstat(verifier._lock_descriptor)
        AnchoredDirectory._require_private_regular(opened_lock)
        if _complete_stat_facts(lock_metadata) != _complete_stat_facts(opened_lock):
            raise ValueError("Phase 2 authority lock changed")
        fcntl.flock(
            verifier._lock_descriptor,
            fcntl.LOCK_SH | fcntl.LOCK_NB,
        )
        locked_path = verifier._state_parent.stat_child(verifier._lock_name)
        if (
            locked_path is None
            or _complete_stat_facts(opened_lock)
            != _complete_stat_facts(locked_path)
        ):
            raise ValueError("Phase 2 authority lock changed")

        payload = _read_stable_private_file(
            verifier._state_parent,
            verifier._state_name,
            max_bytes=MAX_STATE_DB_BYTES,
            expected_metadata=state_metadata,
        )
        connection = sqlite3.connect(":memory:", isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.deserialize(payload)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(_read_only_authorizer)
        verifier.connection = connection
        return verifier
    except Exception:
        verifier.close()
        raise


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("invalid Phase 2 projection")
    return value


def _source_facts(
    *,
    subject_id: str,
    scout_payload: Mapping[str, object],
    filter_payload: Mapping[str, object],
) -> tuple[int, str, str, str]:
    repository = _mapping(scout_payload.get("repository"))
    repository_id = repository.get("id")
    owner = repository.get("owner")
    name = repository.get("name")
    scout_license = repository.get("license_spdx")
    filter_license = filter_payload.get("license_spdx")
    pinned_commit_sha = scout_payload.get("pinned_commit_sha")
    if (
        type(repository_id) is not int
        or repository_id < 1
        or not isinstance(owner, str)
        or _REPOSITORY_PART.fullmatch(owner) is None
        or not isinstance(name, str)
        or _REPOSITORY_PART.fullmatch(name) is None
        or subject_id != f"repo:{owner}/{name}"
        or not isinstance(pinned_commit_sha, str)
        or _COMMIT_SHA.fullmatch(pinned_commit_sha) is None
        or not isinstance(scout_license, str)
        or scout_license not in ALLOWED_LICENSE_SPDX
        or filter_license != scout_license
    ):
        raise ValueError("invalid Phase 2 source facts")
    return (
        repository_id,
        f"https://github.com/{owner}/{name}",
        pinned_commit_sha,
        scout_license,
    )


def _is_verified_rejection_chain(
    *,
    scout_payload: Mapping[str, object],
    filter_payload: Mapping[str, object],
    reader_payload: Mapping[str, object],
    extractor_payload: Mapping[str, object],
) -> bool:
    payloads = (
        scout_payload,
        filter_payload,
        reader_payload,
        extractor_payload,
    )
    vector = tuple(
        (
            stage,
            payload.get("outcome"),
            payload.get("skip_reason"),
        )
        for stage, payload in zip(_PHASE_TWO_STAGES, payloads, strict=True)
    )
    return vector in _VERIFIED_REJECTION_VECTORS


def _validate_local_readme_chain(
    chain: VerifiedRunChain, *, allow: bool,
) -> Mapping[str, object] | None:
    """Recognize scoped evidence and deny it outside explicit local consumers."""
    results = chain.results
    if not any(
        LOCAL_README_SCOPE_KEY in result.payload
        or result.policy_version == LOCAL_README_POLICY_VERSION
        or result.payload.get("policy_version") == LOCAL_README_POLICY_VERSION
        for result in results
    ):
        return None
    if not allow or len(results) != 4:
        raise ValueError("local README evidence is not admitted")
    scope = results[0].payload.get(LOCAL_README_SCOPE_KEY)
    subject = LocalReadmeSubject.model_validate(scope, strict=True)
    canonical_scope = subject.model_dump(mode="json", exclude_none=False)
    if (
        scope != canonical_scope
        or sha256_digest(canonical_scope) != chain.identity.fixture_hash
        or subject.subject_id != chain.identity.subject_id
        or any(result.payload.get(LOCAL_README_SCOPE_KEY) != scope for result in results)
        or results[0].payload.get("ref_requested") != subject.ref
        or (
            results[0].payload.get("outcome") == "accepted"
            and results[0].payload.get("pinned_commit_sha") != subject.ref
        )
    ):
        raise ValueError("local README input identity mismatch")
    reader = results[2]
    if reader.payload.get("outcome") != "accepted":
        return None
    files = reader.payload.get("files")
    if (
        reader.policy_version != LOCAL_README_POLICY_VERSION
        or reader.payload.get("policy_version") != LOCAL_README_POLICY_VERSION
        or not isinstance(files, list)
        or len(files) != 1
    ):
        raise ValueError("invalid local README read plan")
    selected = _mapping(files[0])
    if (
        selected.get("path") != subject.readme_path
        or selected.get("tier") != "readme"
        or type(selected.get("read_order")) is not int
        or selected.get("read_order") != 1
        or type(selected.get("size")) is not int
        or not 0 <= selected["size"] <= READER_ORG_MAX_FILE_BYTES
        or not isinstance(selected.get("blob_sha"), str)
        or _COMMIT_SHA.fullmatch(selected["blob_sha"]) is None
        or not isinstance(selected.get("content_hash"), str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", selected["content_hash"]) is None
        or reader.payload.get("source_code_loaded") is not False
    ):
        raise ValueError("invalid local README file identity")
    budgets = _mapping(reader.payload.get("budgets"))
    if (
        any(type(value) is not int for value in budgets.values())
        or budgets != {
            "files_read": 1, "source_files_read": 0,
            "total_bytes": selected["size"],
            "estimated_input_tokens": estimate_tokens(selected["size"]),
        }
    ):
        raise ValueError("local README budgets disagree with the selected file")
    tree = _mapping(results[0].payload.get("tree"))
    candidates = tree.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("invalid local README tree")
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("path") == subject.readme_path]
    if (
        len(matches) != 1
        or matches[0].get("type") != "blob"
        or matches[0].get("mode") not in {"100644", "100755"}
        or matches[0].get("sha") != selected["blob_sha"]
        or matches[0].get("size") != selected["size"]
    ):
        raise ValueError("local README tree and read plan disagree")
    return selected


class SQLitePhaseTwoCandidateSource:
    """Resolve one strict descriptor without exposing a writable state handle."""

    def __init__(self, path: Path, *, allow_local_readme: bool = False) -> None:
        if type(allow_local_readme) is not bool:
            raise ValueError("invalid local preview permission")
        self._path = Path(path)
        self._allow_local_readme = allow_local_readme

    def resolve(
        self,
        descriptor: CandidateSubjectDescriptorV1,
    ) -> PhaseTwoCandidateProjection:
        try:
            if type(descriptor) is not CandidateSubjectDescriptorV1:
                raise ValueError("invalid candidate descriptor")
            projections = self._resolve_all(
                phase2_run_id=descriptor.phase2_run_id,
                phase2_profile_version=descriptor.phase2_profile_version,
                phase2_producer_version=descriptor.phase2_producer_version,
            )
            matches = [
                projection
                for projection in projections
                if WorkflowSpec.model_validate_json(
                    projection.workflow_spec_bytes,
                    strict=True,
                ).fingerprint
                == descriptor.selected_workflow_fingerprint
            ]
            if len(matches) != 1:
                raise ValueError("ambiguous workflow selection")
            selected = matches[0]
            if (
                selected.extractor_output_hash != descriptor.extractor_output_hash
                or selected.verified_chain_anchor != descriptor.verified_chain_anchor
            ):
                raise ValueError("invalid Phase 2 source anchor")
            return selected
        except CandidateSourceUnavailable:
            raise
        except Exception:
            raise CandidateSourceUnavailable() from None

    def resolve_all(
        self,
        *,
        phase2_run_id: str,
        phase2_profile_version: str,
        phase2_producer_version: str,
    ) -> tuple[PhaseTwoCandidateProjection, ...]:
        try:
            return self._resolve_all(
                phase2_run_id=phase2_run_id,
                phase2_profile_version=phase2_profile_version,
                phase2_producer_version=phase2_producer_version,
            )
        except CandidateSourceUnavailable:
            raise
        except Exception:
            raise CandidateSourceUnavailable() from None

    def _resolve_all(
        self,
        *,
        phase2_run_id: str,
        phase2_profile_version: str,
        phase2_producer_version: str,
    ) -> tuple[PhaseTwoCandidateProjection, ...]:
        verifier: SQLiteStateStore | None = None
        try:
            if (
                type(phase2_run_id) is not str
                or not phase2_run_id
                or phase2_profile_version != PHASE_TWO_PROFILE_VERSION
                or phase2_producer_version != PHASE_TWO_PROFILE_VERSION
            ):
                raise ValueError("invalid Phase 2 identity")
            verifier = _open_read_only_verifier(self._path)
            chain = verifier.verify_run_chain(phase2_run_id)
            local_file = _validate_local_readme_chain(chain, allow=self._allow_local_readme)
            if (
                chain.run.run_id != phase2_run_id
                or chain.run.status is not RunStatus.COMPLETED
                or chain.identity.schema_version != "2"
                or chain.identity.producer_version != phase2_producer_version
                or tuple(result.stage for result in chain.results)
                != _PHASE_TWO_STAGES
                or len(chain.results) != len(_PHASE_TWO_STAGES)
            ):
                raise ValueError("invalid completed Phase 2 chain")

            chain_anchor = sha256_digest(
                chain.model_dump(mode="json", exclude_none=False)
            )
            extractor = chain.results[-1]
            scout_payload = _mapping(chain.results[0].payload)
            filter_payload = _mapping(chain.results[1].payload)
            reader_payload = _mapping(chain.results[2].payload)
            extractor_payload = _mapping(extractor.payload)
            if _is_verified_rejection_chain(
                scout_payload=scout_payload,
                filter_payload=filter_payload,
                reader_payload=reader_payload,
                extractor_payload=extractor_payload,
            ):
                return ()
            if (
                scout_payload.get("outcome") != "accepted"
                or filter_payload.get("outcome") != "accepted"
                or reader_payload.get("outcome") != "accepted"
                or extractor_payload.get("outcome") != "extracted"
            ):
                raise ValueError("Phase 2 source did not succeed")

            workflows = extractor_payload.get("workflows")
            if not isinstance(workflows, list) or not workflows:
                raise ValueError("invalid workflow collection")
            parsed: list[tuple[WorkflowSpec, bytes]] = []
            for candidate in workflows:
                if not isinstance(candidate, Mapping):
                    raise ValueError("invalid workflow projection")
                stored_bytes = canonical_json_bytes(dict(candidate))
                workflow = WorkflowSpec.model_validate_json(stored_bytes, strict=True)
                if local_file is not None:
                    evidence = (*workflow.evidence, *(item for step in workflow.steps for item in step.evidence))
                    if any(
                        (item.path, item.blob_sha, item.content_hash)
                        != (local_file["path"], local_file["blob_sha"], local_file["content_hash"])
                        for item in evidence
                    ):
                        raise ValueError("local README evidence escaped its input")
                canonical_bytes = canonical_json_bytes(
                    workflow.model_dump(mode="json", exclude_none=False)
                )
                if stored_bytes != canonical_bytes:
                    raise ValueError("invalid canonical workflow")
                parsed.append((workflow, stored_bytes))
            fingerprints = tuple(workflow.fingerprint for workflow, _raw in parsed)
            if len(set(fingerprints)) != len(fingerprints):
                raise ValueError("duplicate workflow fingerprints")

            repository_id, repository_url, pinned_commit_sha, license_spdx = (
                _source_facts(
                    subject_id=chain.identity.subject_id,
                    scout_payload=scout_payload,
                    filter_payload=filter_payload,
                )
            )
            return tuple(
                PhaseTwoCandidateProjection(
                    phase2_run_id=phase2_run_id,
                    workflow_spec_bytes=stored_bytes,
                    extractor_output_hash=extractor.output_hash,
                    verified_chain_anchor=chain_anchor,
                    repository_id=repository_id,
                    repository_url=repository_url,
                    pinned_commit_sha=pinned_commit_sha,
                    license_spdx=license_spdx,
                )
                for _workflow, stored_bytes in parsed
            )
        except CandidateSourceUnavailable:
            raise
        except (
            KeyError,
            IndexError,
            MemoryError,
            OSError,
            OverflowError,
            sqlite3.Error,
            TypeError,
            ValidationError,
            ValueError,
        ):
            raise CandidateSourceUnavailable() from None
        except Exception:
            raise CandidateSourceUnavailable() from None
        finally:
            if verifier is not None:
                verifier.close()
