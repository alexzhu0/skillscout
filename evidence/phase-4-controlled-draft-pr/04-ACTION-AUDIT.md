# Phase 4 GitHub Action Supply-Chain Audit

Status: `audited_not_approved` — this is evidence for the separate Gate A4
human decision. It neither authorizes a workflow change nor permits either
action to execute. A release tag is discovery metadata only; the candidate
commit SHA is the only proposed identity.

## Candidate Set for Gate A4

| Repository | Numeric ID | Release metadata (non-authority) | Candidate commit |
|---|---:|---|---|
| `actions/checkout` | 197814629 | `v4.2.2` | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/create-github-app-token` | 595047935 | `v2.1.0` | `67018539274d69449ef7c8cde82c3ff073ffe3b5` |

## Review Scope and Limits

The evidence was collected as static, read-only repository metadata/content:
no checkout, install, import, build, or action execution occurred. Both action
manifests contain no nested `uses:` step. Their checked-in distribution is
JavaScript run by the Actions Node runtime; it can make GitHub/network calls at
job time, so Gate A4 must review the exact bytes and behaviour before any
workflow may reference the candidates.

`actions/checkout` uses Node 20, reads `token`, `repository`, `ref`, and
`ssh-key`, emits `commit`, and uses the supplied token for GitHub REST/git
transport. `actions/create-github-app-token` uses Node 20, reads the App
identity/private-key/repository/permission inputs, emits `token`,
`installation-id`, and `app-slug`, and calls GitHub's App and installation-token
REST endpoints. The latter is the only candidate intended to request contents
and pull-requests write permissions; neither candidate has an install hook or
a nested action dependency.

## Exact Static Evidence

The machine-readable record below is the fixed schema independently checked by
`tools/verify_phase4_action_audit.py`. File digests are SHA-256 of the
read-only content evidence; commit/tree values are Git object SHA-1 values.
The release metadata digest preserves the observed release/ref response for
human review, but never replaces the candidate commit as authority.

<!-- phase4-action-audit
{
  "status":"audited_not_approved",
  "approval":"human_gate_a4_required",
  "candidate_sha_set":["11bd71901bbe5b1630ceea73d27597364c9af683","67018539274d69449ef7c8cde82c3ff073ffe3b5"],
  "actions":[
    {
      "repository_id":197814629,
      "repository_full_name":"actions/checkout",
      "candidate_commit_sha":"11bd71901bbe5b1630ceea73d27597364c9af683",
      "tree_sha":"d0af3a2e48f72b25f2c8a4ce85f9a86058d7eaa7",
      "release_tag_metadata":{"name":"v4.2.2","non_authoritative":true,"authority":"candidate_commit_sha_only"},
      "evidence_files":[
        {"path":"action.yml","sha256":"bc93395a4a6f2a012c91c40c3bf642d4217b8e76e5a25d9310a8a4ed1fa53238","read_only":true},
        {"path":"package.json","sha256":"f1cb3bcd79e4c95fc8ce4e199621292aeaa5735f8d2e55223dd4213f8194cd85","read_only":true},
        {"path":"dist/index.js","sha256":"9d22852010dc49a5c8f0a02c3c4b10a4bb3b5e9dce832cb1d1a77b2235bb879f","read_only":true}
      ],
      "runtime":{"using":"node20","entry":"dist/index.js"},
      "permissions":{"required":["contents:read"],"requested_by_action":[]},
      "nested_actions":[],
      "install_hooks":{"resolved":true,"executable_hooks":[]},
      "behaviour":{"network":"GitHub REST and git transport at runner time","code_execution":"checked-in Node distribution invokes git helpers"},
      "provenance":{"release_metadata_sha256":"e3c36bffdfcdfbbd691a00bf2e9d27f176f1f450d385a6c979f5ab9cc92862cf"},
      "unresolved_claims":[]
    },
    {
      "repository_id":595047935,
      "repository_full_name":"actions/create-github-app-token",
      "candidate_commit_sha":"67018539274d69449ef7c8cde82c3ff073ffe3b5",
      "tree_sha":"eb5e5fc0e85f5c1c4d03aa0c0c51e6fb3e8e6ff8",
      "release_tag_metadata":{"name":"v2.1.0","non_authoritative":true,"authority":"candidate_commit_sha_only"},
      "evidence_files":[
        {"path":"action.yml","sha256":"71bb6500e20692e2f80c4af422513e6090f5b6d1c68c05b00be30d74272608a0","read_only":true},
        {"path":"package.json","sha256":"eafcab61783827354cc3fbaa6b1c14e1db4cb6a34b7fe5e99ca78325a5d30ea6","read_only":true},
        {"path":"dist/index.js","sha256":"00c3762ec818e5f451b69c62a9d55d1ab0ace44bb177678b4ca1db4f5cbfc3a5","read_only":true}
      ],
      "runtime":{"using":"node20","entry":"dist/index.js"},
      "permissions":{"required":["contents:read"],"requested_by_action":["contents:write","pull-requests:write"]},
      "nested_actions":[],
      "install_hooks":{"resolved":true,"executable_hooks":[]},
      "behaviour":{"network":"GitHub App and installation-token REST calls at runner time","code_execution":"checked-in Node distribution parses inputs and requests/revokes token"},
      "provenance":{"release_metadata_sha256":"2e06b487498fc0ab5e2b28689e9d7252b6e18f3c2c9ef7e293c3d7a3399f81d8"},
      "unresolved_claims":[]
    }
  ]
}
-->

## Explicit Non-Authorization

No mutable tag, release, repository name, or this document authorizes action
execution. Plan 08 must either bind an explicit human approval to the exact
two commits and this document's SHA-256, or reject them. Any changed byte,
candidate SHA, tree, evidence digest, nested action, install hook, permission,
runtime, or status invalidates this audit.
