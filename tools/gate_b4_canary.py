"""Dependency-locked, test-only runner for the controlled hosted Gate B4 canary.

This module is deliberately outside ``src``.  It owns a closed request surface,
uses fixed harmless content, emits only bounded canonical evidence, and has no
cleanup, approval, review-submission, ready-for-review, or deletion operation.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NamedTuple, NoReturn

import httpx


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "gate-b4-canary.yml"
ACTION_AUDIT_SHA256 = "f33b1b47c20db6f728522a0e176687c78c19a1d748783f2376d6e28bb67209bb"
SCHEMA_VERSION = "skillscout.gate-b4-canary-evidence.v1"
MAX_RESPONSE_BYTES = 65_536
MAX_EVIDENCE_BYTES = 8_192
MAX_REQUESTS = 24
_SHA = re.compile(r"[0-9a-f]{40}")
_FULL_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
_OWNER_OR_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_RUN_COMPONENT = re.compile(r"[1-9][0-9]{0,19}")
_SAFE_DENIALS = frozenset({"denied", "not_found", "conflict", "validation"})


class CanaryAdmissionError(ValueError):
    """The protected environment did not match the closed canary contract."""


class CanaryRunError(RuntimeError):
    """The hosted canary observed an unsafe or unexpected remote outcome."""

    def __init__(
        self,
        message: str,
        *,
        cleanup_manifest: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.cleanup_manifest = dict(cleanup_manifest or {})


class PreflightConfig(NamedTuple):
    workflow_revision: str
    workflow_sha256: str
    run_id: str
    run_attempt: str
    catalog_repository_id: int
    catalog_full_name: str
    catalog_owner: str
    catalog_repository: str
    expected_installation_id: int
    reviewer: str
    unauthorized_private_repository: str
    branch_prefix: str


class RunConfig(NamedTuple):
    preflight: PreflightConfig
    actual_installation_id: int
    app_token: str


def _required(values: Mapping[str, str], name: str, *, limit: int = 256) -> str:
    value = values.get(name)
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or not value.isascii()
        or any(character in value for character in "\r\n\0")
    ):
        raise CanaryAdmissionError("canary configuration rejected")
    return value


def _positive_integer(value: str) -> int:
    if _RUN_COMPONENT.fullmatch(value) is None:
        raise CanaryAdmissionError("canary configuration rejected")
    parsed = int(value)
    if parsed > 2**63 - 1:
        raise CanaryAdmissionError("canary configuration rejected")
    return parsed


def _workflow_sha256() -> str:
    try:
        payload = WORKFLOW.read_bytes()
    except OSError as error:
        raise CanaryAdmissionError("canary workflow unavailable") from error
    if not payload or len(payload) > 65_536:
        raise CanaryAdmissionError("canary workflow rejected")
    return hashlib.sha256(payload).hexdigest()


def load_preflight_config(env: Mapping[str, str]) -> PreflightConfig:
    """Validate all non-secret authority before an App token can be minted."""

    run_id = _required(env, "GITHUB_RUN_ID", limit=20)
    run_attempt = _required(env, "GITHUB_RUN_ATTEMPT", limit=20)
    if _RUN_COMPONENT.fullmatch(run_id) is None or _RUN_COMPONENT.fullmatch(run_attempt) is None:
        raise CanaryAdmissionError("canary configuration rejected")
    workflow_revision = _required(env, "GITHUB_SHA", limit=40)
    if _SHA.fullmatch(workflow_revision) is None:
        raise CanaryAdmissionError("canary configuration rejected")
    repository_id = _positive_integer(
        _required(env, "SKILLSCOUT_CANARY_CATALOG_REPOSITORY_ID", limit=20)
    )
    expected_installation_id = _positive_integer(
        _required(env, "SKILLSCOUT_CANARY_EXPECTED_INSTALLATION_ID", limit=20)
    )
    full_name = _required(env, "SKILLSCOUT_CANARY_CATALOG_FULL_NAME", limit=201)
    owner = _required(env, "SKILLSCOUT_CANARY_CATALOG_OWNER", limit=100)
    repository = _required(env, "SKILLSCOUT_CANARY_CATALOG_REPOSITORY", limit=100)
    reviewer = _required(env, "SKILLSCOUT_CANARY_REVIEWER", limit=39)
    unauthorized = _required(
        env,
        "SKILLSCOUT_CANARY_UNAUTHORIZED_PRIVATE_REPOSITORY",
        limit=201,
    )
    if (
        _FULL_NAME.fullmatch(full_name) is None
        or _OWNER_OR_REPOSITORY.fullmatch(owner) is None
        or _OWNER_OR_REPOSITORY.fullmatch(repository) is None
        or full_name != f"{owner}/{repository}"
        or _LOGIN.fullmatch(reviewer) is None
        or _FULL_NAME.fullmatch(unauthorized) is None
        or unauthorized == full_name
    ):
        raise CanaryAdmissionError("canary configuration rejected")
    branch_prefix = f"skillscout/gate-b4-{run_id}-{run_attempt}"
    return PreflightConfig(
        workflow_revision=workflow_revision,
        workflow_sha256=_workflow_sha256(),
        run_id=run_id,
        run_attempt=run_attempt,
        catalog_repository_id=repository_id,
        catalog_full_name=full_name,
        catalog_owner=owner,
        catalog_repository=repository,
        expected_installation_id=expected_installation_id,
        reviewer=reviewer,
        unauthorized_private_repository=unauthorized,
        branch_prefix=branch_prefix,
    )


def load_run_config(env: Mapping[str, str]) -> RunConfig:
    """Add late token identity to an already-valid preflight contract."""

    preflight = load_preflight_config(env)
    actual_installation_id = _positive_integer(
        _required(env, "SKILLSCOUT_CANARY_ACTUAL_INSTALLATION_ID", limit=20)
    )
    token = _required(env, "SKILLSCOUT_CANARY_APP_TOKEN", limit=2_048)
    if actual_installation_id != preflight.expected_installation_id:
        raise CanaryAdmissionError("canary installation identity rejected")
    return RunConfig(
        preflight=preflight,
        actual_installation_id=actual_installation_id,
        app_token=token,
    )


def _classification(status_code: int) -> str:
    if status_code in {401, 403, 405}:
        return "denied"
    if status_code == 404:
        return "not_found"
    if status_code == 409:
        return "conflict"
    if status_code == 422:
        return "validation"
    if 200 <= status_code < 300:
        return "success"
    raise CanaryRunError("unexpected GitHub status class")


class _CanaryGitHub:
    def __init__(
        self,
        config: RunConfig,
        *,
        transport: httpx.BaseTransport | None,
    ) -> None:
        self.config = config
        self.repository_path = f"/repos/{config.preflight.catalog_full_name}"
        self.requests = 0
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {config.app_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=httpx.Timeout(10.0),
            transport=transport,
        )

    def close(self) -> None:
        self.client.close()

    def _request(
        self,
        method: str,
        path: str,
        payload: object | None = None,
    ) -> tuple[str, object | None]:
        self.requests += 1
        if (
            self.requests > MAX_REQUESTS
            or method not in {"GET", "POST", "PUT", "PATCH"}
            or not path.startswith("/")
            or len(path) > 512
            or not path.isascii()
        ):
            raise CanaryRunError("closed canary request surface rejected")
        request = self.client.build_request(method, path, json=payload)
        response = self.client.send(request, stream=True)
        try:
            classification = _classification(response.status_code)
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise CanaryRunError("bounded GitHub response rejected")
                chunks.append(chunk)
            if classification != "success":
                return classification, None
            try:
                decoded = json.loads(b"".join(chunks))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise CanaryRunError("GitHub response shape rejected") from error
            return classification, decoded
        finally:
            response.close()

    def required_object(
        self,
        method: str,
        path: str,
        payload: object | None = None,
    ) -> dict[str, Any]:
        classification, decoded = self._request(method, path, payload)
        if classification != "success" or not isinstance(decoded, dict):
            raise CanaryRunError("required GitHub observation rejected")
        return decoded

    def denial(
        self,
        method: str,
        path: str,
        payload: object | None = None,
    ) -> str:
        classification, _ = self._request(method, path, payload)
        if classification not in _SAFE_DENIALS:
            raise CanaryRunError("required GitHub denial not observed")
        return classification


def _nested_sha(payload: Mapping[str, Any], field: str = "object") -> str:
    nested = payload.get(field)
    sha = nested.get("sha") if isinstance(nested, dict) else None
    if not isinstance(sha, str) or _SHA.fullmatch(sha) is None:
        raise CanaryRunError("GitHub SHA observation rejected")
    return sha


def _create_branch(
    github: _CanaryGitHub,
    *,
    branch: str,
    base_sha: str,
) -> None:
    observed = github.required_object(
        "POST",
        f"{github.repository_path}/git/refs",
        {"ref": f"refs/heads/{branch}", "sha": base_sha},
    )
    if observed.get("ref") != f"refs/heads/{branch}" or _nested_sha(observed) != base_sha:
        raise CanaryRunError("created branch observation rejected")


def _write_fixed_content(
    github: _CanaryGitHub,
    *,
    branch: str,
    leaf: str,
    mode: str,
) -> str:
    content = (
        "# SkillScout controlled Gate B4 canary\n\n"
        f"Mode: {mode}\n"
        "This fixed file contains no repository-derived or operator-provided content.\n"
    ).encode("ascii")
    result = github.required_object(
        "PUT",
        f"{github.repository_path}/contents/.skillscout-gate-b4/{leaf}",
        {
            "message": f"chore: controlled Gate B4 {mode} canary",
            "content": base64.b64encode(content).decode("ascii"),
            "branch": branch,
        },
    )
    return _nested_sha(result, "commit")


def _create_pull(
    github: _CanaryGitHub,
    *,
    branch: str,
    base_branch: str,
    draft: bool,
    mode: str,
) -> int:
    pull = github.required_object(
        "POST",
        f"{github.repository_path}/pulls",
        {
            "title": f"SkillScout controlled Gate B4 {mode} canary",
            "body": (
                "Fixed, non-production Gate B4 evidence. "
                "Human/admin cleanup is required; automation will not merge."
            ),
            "head": branch,
            "base": base_branch,
            "draft": draft,
            "maintainer_can_modify": False,
        },
    )
    number = pull.get("number")
    if (
        not isinstance(number, int)
        or number <= 0
        or pull.get("draft") is not draft
        or not isinstance(pull.get("head"), dict)
        or pull["head"].get("ref") != branch
        or not isinstance(pull.get("base"), dict)
        or pull["base"].get("ref") != base_branch
    ):
        raise CanaryRunError("created pull observation rejected")
    return number


def _reviewers(payload: Mapping[str, Any]) -> list[str]:
    users = payload.get("users")
    if not isinstance(users, list):
        raise CanaryRunError("reviewer observation rejected")
    result: list[str] = []
    for user in users:
        login = user.get("login") if isinstance(user, dict) else None
        if not isinstance(login, str) or _LOGIN.fullmatch(login) is None:
            raise CanaryRunError("reviewer observation rejected")
        result.append(login)
    return result


def run_canary(
    config: RunConfig,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object]:
    """Create two fixed canaries, prove denials, and return sanitized evidence."""

    authority = config.preflight
    draft_branch = f"{authority.branch_prefix}-draft"
    merge_branch = f"{authority.branch_prefix}-merge-probe"
    created_branches: list[str] = []
    created_pulls: list[int] = []
    github = _CanaryGitHub(config, transport=transport)
    try:
        installation = github.required_object("GET", "/installation")
        if installation.get("id") != config.actual_installation_id:
            raise CanaryRunError("installation identity mismatch")
        repositories = github.required_object("GET", "/installation/repositories?per_page=100")
        installed = repositories.get("repositories")
        if (
            repositories.get("total_count") != 1
            or not isinstance(installed, list)
            or len(installed) != 1
            or installed[0].get("id") != authority.catalog_repository_id
            or installed[0].get("full_name") != authority.catalog_full_name
        ):
            raise CanaryRunError("installation repository scope mismatch")
        repository = github.required_object("GET", github.repository_path)
        base_branch = repository.get("default_branch")
        if (
            repository.get("id") != authority.catalog_repository_id
            or repository.get("full_name") != authority.catalog_full_name
            or not isinstance(base_branch, str)
            or _OWNER_OR_REPOSITORY.fullmatch(base_branch) is None
        ):
            raise CanaryRunError("catalog repository identity mismatch")
        default_path = f"{github.repository_path}/git/ref/heads/{base_branch}"
        default_before = _nested_sha(github.required_object("GET", default_path))

        _create_branch(github, branch=draft_branch, base_sha=default_before)
        created_branches.append(draft_branch)
        _write_fixed_content(
            github,
            branch=draft_branch,
            leaf=f"gate-b4-{authority.run_id}-{authority.run_attempt}-draft.md",
            mode="draft",
        )
        draft_number = _create_pull(
            github,
            branch=draft_branch,
            base_branch=base_branch,
            draft=True,
            mode="draft",
        )
        created_pulls.append(draft_number)
        github.required_object(
            "POST",
            f"{github.repository_path}/pulls/{draft_number}/requested_reviewers",
            {"reviewers": [authority.reviewer], "team_reviewers": []},
        )
        observed_draft = github.required_object(
            "GET", f"{github.repository_path}/pulls/{draft_number}"
        )
        observed_reviewers = _reviewers(
            github.required_object(
                "GET",
                f"{github.repository_path}/pulls/{draft_number}/requested_reviewers",
            )
        )
        if (
            observed_draft.get("number") != draft_number
            or observed_draft.get("draft") is not True
            or not isinstance(observed_draft.get("head"), dict)
            or observed_draft["head"].get("ref") != draft_branch
            or observed_reviewers != [authority.reviewer]
        ):
            raise CanaryRunError("positive Draft/reviewer evidence rejected")

        _create_branch(github, branch=merge_branch, base_sha=default_before)
        created_branches.append(merge_branch)
        merge_commit = _write_fixed_content(
            github,
            branch=merge_branch,
            leaf=(f"gate-b4-{authority.run_id}-{authority.run_attempt}-merge-probe.md"),
            mode="merge-probe",
        )
        merge_number = _create_pull(
            github,
            branch=merge_branch,
            base_branch=base_branch,
            draft=False,
            mode="merge-probe",
        )
        created_pulls.append(merge_number)
        observed_merge = github.required_object(
            "GET", f"{github.repository_path}/pulls/{merge_number}"
        )
        if (
            observed_merge.get("number") != merge_number
            or observed_merge.get("draft") is not False
            or observed_merge.get("mergeable") is not True
        ):
            raise CanaryRunError("otherwise-mergeable pull evidence rejected")

        denials = {
            "default_ref_mutation": github.denial(
                "PATCH",
                f"{github.repository_path}/git/refs/heads/{base_branch}",
                {"sha": merge_commit, "force": False},
            ),
            "merge": github.denial(
                "PUT",
                f"{github.repository_path}/pulls/{merge_number}/merge",
                {"merge_method": "squash"},
            ),
            "ruleset_read": github.denial("GET", f"{github.repository_path}/rulesets"),
            "ruleset_mutation": github.denial(
                "POST",
                f"{github.repository_path}/rulesets",
                {
                    "name": "skillscout-gate-b4-denial-probe",
                    "target": "branch",
                    "enforcement": "active",
                    "conditions": {
                        "ref_name": {
                            "include": ["~DEFAULT_BRANCH"],
                            "exclude": [],
                        }
                    },
                    "rules": [],
                },
            ),
            "unauthorized_private_repository": github.denial(
                "GET",
                f"/repos/{authority.unauthorized_private_repository}",
            ),
            "secret_metadata_read": github.denial(
                "GET", f"{github.repository_path}/actions/secrets"
            ),
        }
        default_after = _nested_sha(github.required_object("GET", default_path))
        if default_after != default_before:
            raise CanaryRunError("default ref changed during canary")
        return {
            "schema_version": SCHEMA_VERSION,
            "workflow_revision": authority.workflow_revision,
            "workflow_sha256": authority.workflow_sha256,
            "action_audit_sha256": ACTION_AUDIT_SHA256,
            "run": {
                "id": authority.run_id,
                "attempt": authority.run_attempt,
            },
            "installation": {
                "id": config.actual_installation_id,
                "repository_count": 1,
            },
            "catalog": {
                "repository_id": authority.catalog_repository_id,
                "full_name": authority.catalog_full_name,
                "default_branch": base_branch,
            },
            "positive_draft": {
                "branch": draft_branch,
                "pull_number": draft_number,
                "draft": True,
                "requested_reviewers": observed_reviewers,
            },
            "merge_probe": {
                "branch": merge_branch,
                "pull_number": merge_number,
                "draft": False,
                "otherwise_mergeable": True,
            },
            "negative_probes": denials,
            "default_ref": {
                "before": default_before,
                "after": default_after,
                "unchanged": True,
            },
            "cleanup_manifest": {
                "repository": authority.catalog_full_name,
                "branches": created_branches,
                "pulls": created_pulls,
            },
        }
    except CanaryRunError as error:
        raise CanaryRunError(
            "controlled canary failed closed",
            cleanup_manifest={
                "repository": authority.catalog_full_name,
                "branches": created_branches,
                "pulls": created_pulls,
            },
        ) from error
    finally:
        github.close()


def canonical_evidence(evidence: Mapping[str, object]) -> str:
    """Serialize only the closed evidence projection with a strict byte cap."""

    encoded = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    if len(encoded) > MAX_EVIDENCE_BYTES or b"\n" in encoded or b"\r" in encoded:
        raise CanaryRunError("canonical evidence rejected")
    return encoded.decode("ascii") + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", choices=("preflight", "run"))
    return parser


def _fail(cleanup_manifest: Mapping[str, object] | None = None) -> NoReturn:
    evidence: dict[str, object] = {
        "schema_version": "skillscout.gate-b4-canary-error.v1",
        "status": "failed_closed",
    }
    if cleanup_manifest:
        evidence["cleanup_manifest"] = dict(cleanup_manifest)
    print(canonical_evidence(evidence), end="")
    raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        from os import environ

        if arguments.command == "preflight":
            config = load_preflight_config(environ)
            print(
                canonical_evidence(
                    {
                        "schema_version": "skillscout.gate-b4-canary-preflight.v1",
                        "status": "admitted",
                        "workflow_revision": config.workflow_revision,
                        "workflow_sha256": config.workflow_sha256,
                        "action_audit_sha256": ACTION_AUDIT_SHA256,
                        "catalog_repository_id": config.catalog_repository_id,
                        "expected_installation_id": config.expected_installation_id,
                    }
                ),
                end="",
            )
            return 0
        print(canonical_evidence(run_canary(load_run_config(environ))), end="")
        return 0
    except CanaryRunError as error:
        _fail(error.cleanup_manifest)
    except (CanaryAdmissionError, SystemExit):
        _fail()


if __name__ == "__main__":
    raise SystemExit(main())
