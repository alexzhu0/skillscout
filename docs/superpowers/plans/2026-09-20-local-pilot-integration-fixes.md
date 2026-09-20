# Real Markdown pilot integration fixes

The September20 real extraction passed source-fidelity review and pure
qualification (85/100, no hard failure). Export failed deterministically because
the frozen subject says `fabric` and authenticated-free GitHub metadata says
`Fabric`. The verified chain and exact selected-file checks pass; `_source_facts`
alone rejects this case-only difference. GitHub's repository API documents both
owner and repository names as case-insensitive:
https://docs.github.com/en/rest/repos/repos#get-a-repository

The user authorized minimal tested local integration fixes without repeated
approvals. Do not change frozen semantic JSON, old state, model policy, public
schemas, safety/qualification rules, or remote permissions. No model retry.

## Task 1 — match GitHub's case-insensitive repository identity

Use TDD in `tests/test_candidate_source.py` and focused export coverage as needed.
Change only comparison of the complete ASCII owner/repository identity in
`src/skillscout/adapters/phase2_state.py:_source_facts`; preserve metadata spelling
in returned provenance. Case-only owner/repository differences must resolve/export;
different names, suffixes, punctuation, ids/SHAs/licenses remain fail-closed. Do
not normalize or rewrite subjects, manifests, workflows, descriptors or filenames.

## Task 2 — enforce the pilot's single-request build budget

Existing `build-candidate` defaults permit three application attempts per semantic
stage. SDK retries being disabled is insufficient. Add one explicit opt-in
`--single-attempt` to this existing command, with no default/hosted change. It sets
the existing profile's generator/reviewer attempt limits to1 before authority
creation, so the existing profile digest and durable reservations bind the limit.
It does not change models, schemas, retry classification, input/output limits or
validation. This one optional flag is the minimal interface exception needed to
honor the already approved request ceiling; no new command/framework/dependency.

TDD: default remains3/3; opt-in records1/1 in authority; confirmed transient
generator or Reviewer response produces at most one request for that stage;
unknown responses stay terminal; exact descriptor handoff and existing validation
still run. No private monkeypatch of production request behavior.

## Verification and continuation

The prior full suite was deliberately interrupted before any module edit:
1878 passed,1skipped in588.20s, exit2. This is partial evidence, not a passing suite.
After both fixes: focused regressions, Ruff, independent combined review, local
commit, then one complete frozen offline suite. Re-run only local export of the
unchanged verified extraction, never extraction. Only after provenance/qualification
admission can the separately reserved build make one Flash generation and one Pro
review. Failed generation/review ends model work for this pilot. No push or publish.
