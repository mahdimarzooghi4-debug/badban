# Sprint 35 — Multi-source reconciliation source-boundary contract

- Status: Backend source-contract slice; no execution/finance mutation or external provider certification
- Base: main at `1f6b5c2381ea06c92fd49cd13809f2ae8b6d2756`, latest full CI #486 SUCCESS (336 tests)
- Ported and hardened: pure schema, source-target identity, five non-lender source types, source registration and snapshot digest validation from historical PR #16, without importing its conflicting database migrations/Decision 0040 rewrite.
- Scope: typed issuer, custody, settlement, collateral-registry and ledger source records/snapshots, plus legacy lender source representation for future mapping; immutable Pydantic schemas and stable keys.
- Strict protection: exact source type/id/scope and registered versions, canonical SHA-256 hash, evidence presence, coverage bounds, source-timestamp ordering, forbid additional invented fields, no source registered => SOURCE_UNAVAILABLE.
- No assumption that an external source is connected or authoritative. No new comparison outcome, API, policy, limits, stale-age default, fake balance, journal action, reservation, risk PASS, legal issuance, Stage or Production.
- No existing migrations are changed; current LENDER_EXTERNAL_LOAN and resolution/blocking workflow remain untouched. This work is a technical portion of Issue #38, not full BL-042 acceptance.
- Review points: model_copy cannot bypass verification due to revalidation; receipt timestamp not included in semantic source fingerprint; stale threshold intentionally deferred to approved policy; mapped source_id is not proof of legal authorization (caller must check RBAC and legal identity).
