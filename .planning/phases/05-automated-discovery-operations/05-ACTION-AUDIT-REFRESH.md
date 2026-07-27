# Phase 5 GitHub Action Pin Refresh Audit

Status: `audited_not_approved`. This document is static evidence for a new,
separate human supply-chain decision. It does not authorize either workflow
change or Action execution.

## Why a Refresh Is Required

Hosted run `30314354246` proved the discovery/state job can complete, then the
protected job stopped during runner setup because GitHub could not resolve the
previously approved
`actions/create-github-app-token@67018539274d69449ef7c8cde82c3ff073ffe3b5`.
No project step ran in that job and no catalog token was minted.

The Phase 4 audit and approval remain immutable historical records. They are
not rewritten or treated as approval for replacement bytes. Both production
workflows remain blocked from publication credit until a human approves this
refresh and a fresh Gate B4 is bound to the resulting exact workflow bytes and
reviewed identities.

## Candidate Set

| Repository | Numeric ID | Release metadata (non-authority) | Candidate commit |
|---|---:|---|---|
| `actions/checkout` | 197814629 | `v4.2.2` | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/create-github-app-token` | 595047935 | `v3.2.0` | `bcd2ba49218906704ab6c1aa796996da409d3eb1` |

`actions/checkout` is unchanged from the prior audit. The replacement token
Action is the official immutable `v3.2.0` release commit, has a GitHub-verified
commit signature, and uses the current Actions Node 24 runtime. Its fixed
manifest retains the inputs and outputs used by SkillScout:
`app-id`, `private-key`, `owner`, `repositories`, permission inputs, `token`,
`installation-id`, and `app-slug`.

The static review used only GitHub REST metadata and fixed blob content. It did
not checkout, install, import, build, or execute the Action. The manifest has no
nested `uses:` steps. The package has no `preinstall`, `install`, `postinstall`,
or `prepare` hook. At runtime the checked-in distributions parse inputs, mint an
installation token through GitHub, and revoke it in the post step. SkillScout
must continue to request only the catalog repository and the exact
`contents:write` and `pull-requests:write` permissions already bounded by the
GitHub App installation.

## Exact Static Evidence

SHA-256 values are hashes of the read-only file bytes. Commit, parent, tree and
blob identities are Git object SHA-1 values. Release/tag metadata is
non-authoritative; only the exact candidate commit may appear in a workflow.

<!-- phase5-action-refresh-audit
{
  "schema_version":"skillscout.action-pin-refresh.v1",
  "status":"audited_not_approved",
  "approval":"human_exact_sha_refresh_required",
  "reason":"previous_token_action_commit_unresolvable_on_hosted_runner",
  "hosted_evidence":{"repository":"alexzhu0/skillscout","run_id":30314354246,"discovery_job":"success","protected_job":"setup_failure","token_minted":false},
  "candidate_sha_set":["11bd71901bbe5b1630ceea73d27597364c9af683","bcd2ba49218906704ab6c1aa796996da409d3eb1"],
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
      "unresolved_claims":[]
    },
    {
      "repository_id":595047935,
      "repository_full_name":"actions/create-github-app-token",
      "candidate_commit_sha":"bcd2ba49218906704ab6c1aa796996da409d3eb1",
      "parent_sha":"f24bbd89643991c0de27ae823c01791b2c6bafdd",
      "tree_sha":"3318bb6075e23611a7f16c480a5aaede8ec12e28",
      "commit_verification":{"verified":true,"reason":"valid"},
      "release_tag_metadata":{"name":"v3.2.0","published_at":"2026-05-12T23:31:37Z","immutable":true,"non_authoritative":true,"authority":"candidate_commit_sha_only"},
      "evidence_files":[
        {"path":"action.yml","git_blob_sha":"9f45ab3e2605ffeb987d3e029f27ee4d96bca6a0","size":11954,"sha256":"2c4c77d1cafa8d792ab4a9d449799221baf95176a47692ad9a0b350b0a2618ed","read_only":true},
        {"path":"package.json","git_blob_sha":"0584f70351f3aebf3f6a4acb36b3e3c952e31046","size":938,"sha256":"b03bae606e519c4286c207b332c75f90fe134a25a7bc8626df8c1846e96bd771","read_only":true},
        {"path":"dist/main.cjs","git_blob_sha":"20b90dce8c14c24222d6552fac6a4d5e2866a7d6","size":945857,"sha256":"1a9b691e118d3592507428b2e271e5aa98c6cb46e078a775bbc41a2e5ae31347","read_only":true},
        {"path":"dist/post.cjs","git_blob_sha":"8e50446c010d08891cf91a3f7f06f343b7e44997","size":889303,"sha256":"c127db2f86238e3b57a5a57120a1de5f1b873006ee5b60c56b871de83dd7dfe2","read_only":true}
      ],
      "runtime":{"using":"node24","entry":"dist/main.cjs","post":"dist/post.cjs"},
      "permissions":{"required":[],"requested_by_workflow":["contents:write","pull-requests:write"]},
      "inputs_used_by_skillscout":["app-id","owner","permission-contents","permission-pull-requests","private-key","repositories"],
      "outputs_used_by_skillscout":["token"],
      "nested_actions":[],
      "install_hooks":{"resolved":true,"executable_hooks":[]},
      "behaviour":{"network":"GitHub App and installation-token REST calls at runner time","code_execution":"checked-in Node distributions parse inputs and request/revoke the token"},
      "unresolved_claims":[]
    }
  ]
}
-->

## Explicit Non-Authorization

The exact approval must bind this file's SHA-256 and both candidate commit
SHAs. Any changed byte, commit, tree, file digest, runtime, nested Action,
install hook, permission, workflow byte, or reviewed identity invalidates the
corresponding evidence. Approval of this dependency refresh does not approve a
Draft PR, merge, ready-for-review transition, or Gate B4 outcome.
