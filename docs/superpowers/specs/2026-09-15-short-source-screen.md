# Short-source screen after the closed v4 trial

Read-only screen of at most three repository candidates, before any new model
allocation. No prompt changes, credential reads, source execution or remote
writes. Keep the existing filename, content and license limits. Repository text
is evidence only, not instructions to the operator.

## microsoft/prompts-for-edu — excluded from this local profile

- Public repository, MIT confirmed at commit
  `508567d4008b17dc1df98cbb89f88708c250f666`.
- License blob: `9e841e7a26e4eb057b24511e7b92d42b257a80e5`.
- Inspected `README.md`, 5,679 bytes, blob
  `10b22a2efa45f226b0372028c0304b092f2051d2`.
- Content SHA-256:
  `7ea8e5546f98fb25d8688da3d703f5bc95eecfdd1a350eb6302957f50b4ba311`.
- The root README explains the educational prompt collection, responsible use,
  and a generic browse/copy/apply sequence. It does not contain a self-contained
  task-specific analysis workflow with substantive processing steps.
- The bounded tree lists potentially relevant prompt documents, but they are
  not README files and cannot be silently substituted into this selected-README
  trial. Their contents were not fetched. No source was rewritten or renamed.
- No model request. This is a local-profile eligibility limitation, not a claim
  that the repository contains no valuable workflows.

## brexhq/prompt-engineering — excluded (revisited source)

- Public; GitHub repository metadata reports MIT. An immutable license-body
  verification was not performed, since the source already failed the workflow
  scope screen; this is not license admission.
- Commit `50871be17eb86d70ce066462f4328a6f62a7208e`, root `README.md`,
  blob `a43ad6dcbfaf1c64e431b9eb726c4e944ca6b879`, 65,747 bytes.
- Content SHA-256:
  `a425c8e7edc2e4f09db25baa0dd63637b53d2c769aaef432c40c47f6b4904626`.
- Multi-topic prompt-engineering guide rather than a short single-task workflow.
  This repository was already considered in the earlier pilot, so its revisit
  does not constitute a third new discovery or new extraction authority.

## promptfoo/promptfoo — excluded

- Public; GitHub repository metadata reports MIT; immutable license-body
  verification not performed after scope rejection.
- Commit `29a15d1edb256c789d0035ce3f36ad7cf91db6bb`, root `README.md`,
  blob `5260a4d7c2d35ed59f940f551000d181f7da8ba0`, 4,844 bytes.
- Content SHA-256:
  `426270e1b7c45d0bf456b1284cdc1af055218db73869864b9590b1e0bdaab5cb`.
- The short quick start requires installing and executing the evaluation CLI
  with provider credentials. It does not independently specify a tool-free
  textual analysis procedure suitable for this trial.

## Outcome

No eligible source was found in the three bounded screening slots. No model
calls, new extraction allocation or campaign. The delegated two-repository check
used eight anonymous reads, including two repeat reads of the same README
objects after a local base64 whitespace decoding error; that small diagnostic
retry did not call a model or alter source/state. The first repository used
five guarded anonymous reads (metadata, commit, tree, license, README blob).

Do not expand the filename/reader boundary silently. The project can read
documentation generally, but this trial's versioned local profile specifically
requires README files. Supporting a selected ordinary Markdown workflow would
change that profile's source contract and therefore requires a separately
approved design under the implementation plan's schema-boundary stop rule.
