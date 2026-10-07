# Decision 0040 — Sprint 14 Multi-Source Reconciliation Completion Authorization

- **Status:** Accepted
- **Date:** 2026-10-07
- **Authority:** Explicit Product Owner continuation of Sprint 14 / BL-042
- **Depends on:** Decision 0039; Technical 04/06/09/10

Complete the five remaining BL-042 acquisition/comparison capability paths within
Sprint 14. This supersedes the lender-only executable acquisition boundary in the
Sprint plan, without authorizing a new Sprint or changing policy governance.
Authorize only read-only source ports, strict canonical snapshots, deterministic
identity/scope, internal snapshot builders, comparison execution, tests and docs.
BL-042 does not require implementing BL-022 to define an issuer snapshot port.

Keep exactly LENDER, GUARANTEE_ISSUER, CUSTODY, SETTLEMENT, COLLATERAL_REGISTRY and
LEDGER. External non-lenders use actual ACTIVE LegalEntity plus the appropriate
currently VALID LegalAuthorization role: GUARANTEE_ISSUER, CUSTODIAN,
PAYMENT_PROVIDER or COLLATERAL_REGISTRY_OPERATOR. Reuse the existing effective
window and unscoped authorization semantics; scoped authorizations remain closed
until a capability-scope matcher exists. Never create a CreditProvider stand-in.

Legal-source Pack scope is exactly `{pilot_scope, legal_entity_id, role_code}`;
component scope adds reconciliation_type. Resolve one effective ACTIVE pack,
then its exact approved immutable pinned component with hash proof. No caller
pilot scope, policy IDs, global fallback, first match or latest substitution.
LEDGER takes Program identity, derives its legal entity from Program, requires
both ACTIVE and binds `{pilot_scope, program_id, legal_entity_id}`. Program is
already a real JournalPosting dimension. It creates no external provider.
Actor grants are checked at LEGAL_ENTITY or PROGRAM; lender PROVIDER grants and
legacy provider_id-only requests remain compatible.

Each source has its own strict canonical record model and a versioned, hashed
snapshot preserving source/scope, observed/received times, optional coverage and
watermark, mapping/contract/schema versions and explicit evidence. Source ports
are read-only. Runtime registries start empty; absent implementations are source
unavailable, never empty successful snapshots. Test ports live only in tests.

Internal acquisition uses actual GuaranteeCase and CreditProductVersion fields,
AssetPosition/AssetType, or POSTED JournalEntry/JournalPosting and account taxonomy.
Custody matching uses source + position ID + the position's source_reference;
source ports must return that exact custody reference and explicit position ID.
Do not infer ownership/control/restriction or release states not represented by
those rows. Source_reference is a comparison binding, not proof of legal control.
GuaranteeCase.updated_at is a fact freshness timestamp, never legal issued_at.
A configured comparison for absent issued_at yields missing evidence, not match.

Journal balances group all implemented posting dimensions, currency, account,
ledger layer and normal-balance convention. Debit/Credit balances use the existing
taxonomy; MEMO lacks a directional balance interpretation and fails closed. No
synthetic zero group is created. A typed read-only sub-ledger port supplies the
other side; no concrete projection currently exists and no fixture is registered
at runtime. Reconciliation never changes journal truth.

Two acquisition subpaths remain contract-blocked in current internal models:
SETTLEMENT has a journal settlement_reference but no source-legal-entity-to-cash-
transaction binding, cash account selection, payer/payee/value-date or external
settlement-state mapping; a journal row alone is not cash settlement evidence.
COLLATERAL_REGISTRY has no implemented BackingAllocation/legal registration
identity or restriction model. Do not derive legal registration from asset rows.
Their external ports and comparisons may execute and retain external-only evidence,
but internal acquisition is explicitly unavailable. These gaps must not be marked
as matched or the entire backlog item marked complete. Normal owning-domain
contracts must resolve the gaps; do not implement BL-020/022/023/026 to bypass them.

Migration 0016 may add only typed legal/program run identity and nullable internal
cutoff (absent evidence has no invented cutoff). Published 0015 stays unchanged.
History remains immutable; downgrade refuses incompatible multi-source history.
No per-source tables or raw arbitrary provider-payload storage.

Exclude BL-022, BL-020, BL-023, BL-026, BL-043 human resolution, provider commands/
events/credentials/real integrations, production policy values, UI, Stage, QA gate,
Release and Production. No guarantee issuance, custody mutation, cash movement or
registry mutation. PR #9 stays untouched. Continue the same PR #16, Draft/Open,
unmerged; green exact-HEAD CI and a new exact-HEAD review are required.

One shared execution pipeline handles all six types. The lender wrapper is a
read-only bridge to the existing registered adapter and preserves its contract,
mapping and inbound-normalization versions. It fabricates no adapter. Acquisition
received_at is measured with the service clock, not copied from observed_at.
Optional absent coverage/watermark/normalization metadata stays explicitly absent.

Technical 10 explicitly classifies a missing authoritative custody position as
CRITICAL unless policy classifies transient provider lag. The strict schema adds
an optional custody-only `custody_missing_external_transient_lag` boolean. Only an
explicit true classification enables the existing missing-record materiality map;
absence or false preserves the accepted CRITICAL invariant. No numeric policy
value or production exemption is seeded; unrelated policy semantics stay intact.
Long stable source references remain exact matching inputs; bounded persisted
resource IDs use their canonical hash where necessary, with original canonical
references preserved in observations. This is not fuzzy matching.
