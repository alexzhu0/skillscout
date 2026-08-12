---
phase: 01
slug: auditable-dry-run-spine
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-21
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| CLI ↔ fixture input | Frozen JSON/SQLite fixtures read via one-descriptor bounded controls | Untrusted file bytes (TOCTOU, size, identity) |
| Pipeline ↔ SQLite state | Transactional state/checkpoint/event persistence with chain verification | Run identities, stage envelopes, resume authority |
| Pipeline ↔ local filesystem | Descriptor-anchored atomic replacement under kernel flocks | State db, manifests, backups, publication plan, stale temps |
| Evidence tool ↔ subprocess/cwd | Independent record/verify from external cwd, pinned offline toolchain | Digests, command claims, fixture authority |
| Dry-run ↔ remote write | Architecturally absent — sealed none/local-state composition, no network imports | None (capability omission, socket sentinel) |

---

## Threat Register

All 83 register rows from `01-01-PLAN.md` … `01-18-PLAN.md` `<threat_model>` blocks (73 unique IDs; T-01-SC recurs across plans as the supply-chain lock-gate row). Every row is disposition `mitigate`; every mitigation verified present in implementation by the 2026-07-21 audit (gsd-security-auditor, ASVS L1 — symbol-level spot checks plus 302 security-relevant tests rerun green).

| Group | Threats | Severity range | Status |
|-------|---------|----------------|--------|
| T-01-SC* (supply-chain gate, all plans) | 18 | high | closed |
| T-01-01 … T-01-08 (fixture/input boundary) | 10 | high–critical | closed |
| T-01-12, T-01-G1-*, T-01-G2-*, T-01-G3-*, T-01-G4-* (state, pipeline, capability firewall) | 24 | medium–critical | closed |
| T-01-FINAL-* (zero-network acceptance) | 4 | high–critical | closed |
| T-01-12-* … T-01-16-* (recovery, resume authority, evidence) | 25 | high–critical | closed |
| T-01-17-* (stale-temp crash recovery) | 5 | medium–high | closed |
| T-01-18-* (evidence authority) | 5 | medium–high | closed |

*Status: open · closed · open — below high threshold (non-blocking). All 83 rows: closed.*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Deferred (non-blocking, tracked in 01-GAP-VALIDATION.md `deferred`): OS/syscall-level outbound-network denial — Phase 6 scope; Phase-1 mitigation (capability omission + socket sentinel) present and tested.

---

## Accepted Risks Log

No accepted risks.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-21 | 83 | 83 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-21
