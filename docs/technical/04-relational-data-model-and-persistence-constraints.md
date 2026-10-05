# Badban Relational Data Model and Persistence Constraints

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; System Context; Domain Aggregate Boundaries; State Machines and Transition Contracts

## 1. Objective

Define a relational persistence model that enforces Badban's core financial and lifecycle invariants at both application and database levels.

This document is a logical relational contract. The exact database product is selected in the deployment/runtime architecture, but the chosen engine must support:

- ACID transactions;
- foreign keys;
- unique constraints;
- check constraints;
- transactional row locking or equivalent concurrency control;
- reliable indexes;
- timezone-aware timestamps;
- high-precision decimal/numeric values;
- transactional outbox/inbox persistence.

## 2. Global Persistence Rules

All mutable aggregate-root tables must contain at least:

- `id` — globally unique identifier;
- `version` — monotonically increasing aggregate version for optimistic concurrency;
- `created_at`;
- `updated_at`;
- `created_by` / actor reference where applicable.

Rules:

1. financial/history records are append-only unless explicitly defined as mutable aggregate state;
2. posted journal entries, accepted valuations, processed provider events, audit events, and active policy versions are immutable;
3. user-facing deletion must be logical/status-based, not physical deletion, for regulated/financial records;
4. timestamps are stored as timezone-aware values;
5. all monetary/quantity values use exact decimal/numeric types;
6. no binary floating-point column is permitted for monetary value, price, quantity used in financial calculation, guarantee amount, exposure, reserve, claim, or allocation.

## 3. Identifier Strategy

Use opaque globally unique IDs for internal identifiers.

Recommended logical types:

- UUID/ULID-equivalent for aggregate/entity IDs;
- external provider IDs stored separately as text/reference fields;
- human-readable reference numbers generated independently where needed.

External IDs must never be reused as Badban primary keys.

For provider-scoped external identifiers, enforce uniqueness on:

```
(provider_id, external_identifier_type, external_identifier)
```

where applicable.

## 4. Participant and Program Tables

### participants

Columns:

- id PK;
- external_reference nullable;
- lifecycle_status;
- created_at;
- updated_at.

This table contains identity linkage only.

Sensitive identity/profile data should be isolated from transactional finance data where practical.

### programs

Columns:

- id PK;
- code UNIQUE;
- name;
- status;
- legal_entity_id nullable;
- created_at;
- updated_at.

### participation_episodes

Columns:

- id PK;
- participant_id FK participants;
- program_id FK programs;
- status;
- eligibility_reference;
- consent_state;
- started_at;
- ended_at nullable;
- version;
- created_at;
- updated_at.

Constraints:

- `ended_at >= started_at` when ended_at is not null;
- status transition controlled in application layer;
- no physical reuse of a closed episode;
- re-entry creates another row.

Indexes:

- participant_id;
- program_id;
- (participant_id, program_id, status).

## 5. Legal Entity and Authorization Tables

### legal_entities

Columns:

- id PK;
- legal_name;
- registration_identifier;
- entity_type;
- status;
- created_at;
- updated_at.

Unique:

- registration_identifier when available.

### legal_roles

Reference table or constrained enum-like table:

- GUARANTEE_ISSUER;
- LENDER;
- CUSTODIAN;
- ASSET_MANAGER;
- PAYMENT_PROVIDER;
- COLLATERAL_REGISTRY_OPERATOR;
- BADBAN_CORE;
- other approved roles.

### legal_entity_authorizations

Columns:

- id PK;
- legal_entity_id FK;
- role_code;
- regulator_or_authority;
- authorization_reference;
- scope_definition;
- valid_from;
- valid_until nullable;
- status;
- evidence_reference nullable;
- last_reviewed_at;
- version;
- created_at;
- updated_at.

Constraints:

- valid_until > valid_from when valid_until exists;
- status cannot be VALID when current authorization evidence is missing if policy requires evidence;
- no new regulated action when status != VALID.

Indexes:

- (legal_entity_id, role_code, status);
- valid_until;
- regulator_or_authority.

## 6. Credit Provider and Product Tables

### credit_providers

Columns:

- id PK;
- legal_entity_id FK legal_entities;
- provider_code UNIQUE;
- status;
- integration_mode;
- authorization_review_state;
- suspension_reason nullable;
- version;
- created_at;
- updated_at.

Constraint:

- one provider maps to exactly one legal entity.

### credit_product_versions

Columns:

- id PK;
- provider_id FK;
- product_code;
- version_number;
- lifecycle_status;
- currency;
- min_principal nullable;
- max_principal nullable;
- tenor_definition;
- repayment_definition;
- pricing_definition;
- guarantee_mode;
- delinquency_definition;
- claim_definition;
- effective_from;
- effective_to nullable;
- created_at;
- approved_at nullable.

Unique:

```
(provider_id, product_code, version_number)
```

Constraints:

- min_principal >= 0;
- max_principal >= min_principal when both set;
- effective_to > effective_from when set;
- active versions immutable;
- one-to-one loan/guarantee rule is not stored as an optional switch for the pilot.

Indexes:

- (provider_id, lifecycle_status);
- (provider_id, product_code, effective_from).

## 7. Asset Type Tables

### asset_types

Columns:

- id PK;
- asset_code UNIQUE;
- name;
- status;
- unit_code;
- quantity_scale;
- currency_or_valuation_currency;
- version;
- created_at;
- updated_at.

### asset_type_policy_versions

Columns:

- id PK;
- asset_type_id FK;
- version_number;
- lifecycle_status;
- valuation_source_definition;
- advance_rate;
- pledgeability_definition;
- revaluation_rule;
- stale_after_duration;
- concentration_rule_reference;
- custody_rule_reference;
- enforcement_rule_reference;
- effective_from;
- effective_to nullable;
- approved_at nullable;
- created_at.

Unique:

```
(asset_type_id, version_number)
```

Checks:

- `0 <= advance_rate AND advance_rate <= 1`;
- effective_to > effective_from when present.

No active transaction may use a DRAFT policy version.

## 8. Asset Position Tables

### asset_positions

Columns:

- id PK;
- participation_episode_id nullable FK;
- program_id nullable FK;
- asset_type_id FK;
- ownership_funding_type;
- legal_owner_entity_id nullable FK;
- legal_owner_participant_id nullable FK;
- custodian_legal_entity_id nullable FK;
- quantity;
- unit_code;
- lifecycle_status;
- source_reference;
- version;
- created_at;
- updated_at.

Checks:

- quantity >= 0;
- exactly one permitted ownership owner pattern must be satisfied according to ownership_funding_type;
- unit_code must match Asset Type policy;
- ownership_funding_type cannot be null.

Pilot recommendation:

For initial implementation, constrain ownership_funding_type to approved values:

- PARTICIPANT_OWNED;
- PROGRAM_ATTRIBUTED.

### asset_position_restrictions

Columns:

- id PK;
- asset_position_id FK;
- restriction_type;
- source_type;
- source_id;
- quantity_restricted nullable;
- capacity_amount_restricted nullable;
- status;
- effective_from;
- released_at nullable;
- version;
- created_at.

Unique active restriction by source:

```
(asset_position_id, source_type, source_id, restriction_type)
```

where status is active, implemented through application validation and partial unique index if supported.

## 9. Valuation Tables

### valuation_observations

Columns:

- id PK;
- asset_position_id FK;
- asset_type_policy_version_id FK;
- valued_quantity;
- unit_price;
- valuation_currency;
- fx_rate nullable;
- gross_market_value;
- source_name;
- source_reference;
- observed_at;
- received_at;
- freshness_status;
- evidence_reference nullable;
- created_at.

Immutability:

- no UPDATE after accepted insertion;
- correction creates a new observation.

Checks:

- valued_quantity >= 0;
- unit_price >= 0;
- gross_market_value >= 0;
- fx_rate > 0 when present;
- received_at >= observed_at only if source semantics require it; do not assume clock ordering for asynchronous providers if not reliable.

Indexes:

- (asset_position_id, observed_at DESC);
- (freshness_status, observed_at);
- source_reference.

## 10. Policy Pack Tables

### policy_packs

Columns:

- id PK;
- policy_pack_code;
- version_number;
- scope_code;
- lifecycle_status;
- effective_from nullable;
- effective_to nullable;
- reviewed_at nullable;
- approved_at nullable;
- activated_at nullable;
- created_by;
- approved_by nullable;
- created_at.

Unique:

```
(policy_pack_code, version_number)
```

### policy_pack_components

Columns:

- id PK;
- policy_pack_id FK;
- component_type;
- component_reference_id;
- component_version;
- created_at.

Unique:

```
(policy_pack_id, component_type, component_reference_id)
```

Constraint:

- ACTIVE policy pack immutable;
- only one ACTIVE policy pack per pilot scope unless segmented scope is explicitly added later.

## 11. Guarantee Tables

### guarantee_cases

Columns:

- id PK;
- participation_episode_id FK;
- provider_id FK;
- credit_product_version_id FK;
- policy_pack_id FK;
- state;
- requested_principal;
- reserved_guarantee_amount nullable;
- issued_guarantee_amount nullable;
- current_guarantee_exposure;
- guarantee_mode;
- reservation_expires_at nullable;
- legal_guarantee_external_id nullable;
- legal_guarantee_issuer_id nullable FK legal_entities;
- external_loan_mirror_id nullable;
- risk_snapshot_id nullable;
- version;
- created_at;
- updated_at;
- closed_at nullable.

Checks:

- requested_principal > 0;
- monetary amounts >= 0;
- current_guarantee_exposure >= 0;
- issued_guarantee_amount <= reserved_guarantee_amount when both present, except an atomic amendment workflow;
- closed_at only when terminal/closed state.

Unique:

- legal guarantee ID scoped to guarantee issuer when present.

Indexes:

- participation_episode_id;
- provider_id;
- state;
- reservation_expires_at;
- legal_guarantee_external_id.

### guarantee_state_history

Append-only.

Columns:

- id PK;
- guarantee_case_id FK;
- from_state;
- to_state;
- command_id;
- actor_id/system_id;
- reason_code;
- evidence_reference nullable;
- policy_pack_id;
- occurred_at;
- aggregate_version_after;
- correlation_id;
- causation_id.

Unique:

- command_id within command-processing scope.

## 12. Backing Allocation Tables

### backing_allocations

Columns:

- id PK;
- guarantee_case_id FK;
- state;
- total_capacity_amount;
- version;
- created_at;
- updated_at.

Recommended pilot constraint:

- one active backing allocation root per guarantee case.

### backing_allocation_items

Columns:

- id PK;
- backing_allocation_id FK;
- asset_position_id FK;
- valuation_observation_id FK;
- capacity_amount;
- reserved_amount;
- encumbered_amount;
- released_amount;
- state;
- version;
- created_at;
- updated_at.

Checks:

- all amounts >= 0;
- released_amount <= capacity_amount;
- reserved_amount <= capacity_amount;
- encumbered_amount <= capacity_amount.

Logical invariant:

```
sum(item.capacity_amount)
= backing_allocation.total_capacity_amount
```

must be checked transactionally by application service and, where practical, by deferred database validation/triggers.

### asset_capacity_locks

Optional explicit concurrency table if needed.

Columns:

- asset_position_id PK/FK;
- aggregate_version;
- reserved_capacity;
- active_encumbered_capacity;
- other_hold_capacity;
- updated_at.

This is a transactional concurrency projection, not the historical financial source.

Rules:

- updated inside the same transaction as reservation/release;
- guarded by row-level lock or serializable equivalent;
- never independently edited by operations users.

## 13. External Loan Mirror Tables

### external_loan_mirrors

Columns:

- id PK;
- guarantee_case_id UNIQUE FK;
- provider_id FK;
- external_loan_id;
- state;
- original_principal;
- outstanding_principal;
- currency;
- disbursed_at nullable;
- settled_at nullable;
- delinquency_state nullable;
- last_provider_event_at nullable;
- last_synced_at nullable;
- reconciliation_status;
- version;
- created_at;
- updated_at.

Unique:

```
(provider_id, external_loan_id)
```

Checks:

- original_principal > 0;
- outstanding_principal >= 0;
- outstanding_principal <= original_principal unless an explicit correction workflow proves provider correction;
- for ACTIVE pilot loans:
  `original_principal = guarantee_cases.issued_guarantee_amount`.

The final equality is a cross-table invariant enforced by activation transaction logic and optionally a deferred database assertion/trigger if supported.

### external_loan_events

Append-only.

Columns:

- id PK;
- external_loan_mirror_id FK;
- provider_event_id;
- event_type;
- principal_delta nullable;
- outstanding_principal_reported nullable;
- provider_event_at;
- received_at;
- evidence_reference nullable;
- payload_hash nullable;
- processed_status;
- created_at.

Unique:

```
(provider_id or mirror scope, provider_event_id)
```

Duplicate provider events must be rejected/deduplicated before financial effects.

## 14. Risk and Reserve Tables

### portfolio_risk_snapshots

Append-only.

Columns:

- id PK;
- policy_pack_id FK;
- risk_state;
- total_active_exposure;
- total_reserved_exposure;
- committed_exposure;
- approved_portfolio_limit;
- reserve_requirement;
- reserve_available;
- concentration_metrics_reference;
- stress_result_reference nullable;
- evaluated_at;
- created_at.

Checks:

- all monetary metrics >= 0;
- risk_state in GREEN/AMBER/RED.

### reserve_accounts

Columns:

- id PK;
- legal_entity_id FK;
- reserve_type;
- currency;
- status;
- ledger_account_reference;
- version;
- created_at;
- updated_at.

Reserve account types may include:

- CLAIM_SETTLEMENT_LIQUIDITY;
- EXPECTED_LOSS;
- STRESS_BUFFER.

Balances must be derived from ledger, not directly stored as authoritative mutable values.

## 15. Claim Tables

### guarantee_claims

Columns:

- id PK;
- guarantee_case_id FK;
- lender_claim_reference;
- state;
- requested_amount;
- eligible_amount nullable;
- approved_amount nullable;
- rejected_amount nullable;
- settlement_amount nullable;
- submitted_at;
- decided_at nullable;
- settled_at nullable;
- decision_reason_code nullable;
- version;
- created_at;
- updated_at.

Unique:

- (guarantee_case_id, lender_claim_reference) when lender reference exists.

Checks:

- amounts >= 0;
- approved_amount <= eligible_amount;
- settlement_amount <= approved_amount;
- approved_amount cannot exceed eligible current exposure at decision time; enforced transactionally.

### claim_evidence

Columns:

- id PK;
- guarantee_claim_id FK;
- evidence_type;
- external_reference;
- evidence_hash nullable;
- verified_status;
- verified_at nullable;
- created_at.

## 16. Recovery Tables

### recovery_cases

Columns:

- id PK;
- guarantee_claim_id FK;
- guarantee_case_id FK;
- state;
- allocation_method;
- total_recovered_amount;
- enforcement_costs;
- residual_shortfall nullable;
- participant_surplus nullable;
- program_surplus nullable;
- version;
- created_at;
- updated_at;
- closed_at nullable.

Checks:

- monetary fields >= 0 unless a specific signed adjustment record is used;
- closed state requires allocation finalized.

### recovery_receipts

Append-only.

Columns:

- id PK;
- recovery_case_id FK;
- source_type;
- external_receipt_reference nullable;
- amount;
- received_at;
- evidence_reference;
- idempotency_key;
- created_at.

Unique:

- idempotency_key;
- external receipt reference within source scope.

## 17. Return Allocation Tables

### return_allocation_events

Columns:

- id PK;
- participation_episode_id nullable FK;
- program_id nullable FK;
- source_return_reference;
- policy_pack_id FK;
- state;
- eligible_net_return;
- risk_reserve_amount;
- livelihood_amount;
- future_financial_amount;
- capital_growth_amount;
- social_reinvestment_amount;
- carry_forward_amount;
- allocation_profile;
- version;
- created_at;
- approved_at nullable;
- posted_at nullable.

Checks:

- every allocation amount >= 0;
- exact balance:

```
eligible_net_return =
risk_reserve_amount
+ livelihood_amount
+ future_financial_amount
+ capital_growth_amount
+ social_reinvestment_amount
+ carry_forward_amount
```

This equality should be enforced with a database CHECK when the database numeric model permits deterministic exact arithmetic.

## 18. Future Financial Entitlement Tables

### future_financial_entitlements

Columns:

- id PK;
- participation_episode_id FK;
- policy_pack_id FK;
- status;
- vested_amount;
- unvested_amount;
- paid_amount;
- currency;
- version;
- created_at;
- updated_at.

Checks:

- amounts >= 0;
- paid_amount <= vested_amount;
- remaining payable is derived, not independently edited.

### future_financial_payments

Append-only.

Columns:

- id PK;
- entitlement_id FK;
- amount;
- external_settlement_reference nullable;
- payment_state;
- effective_at;
- idempotency_key;
- created_at.

Unique:

- idempotency_key.

## 19. Exit Tables

### participant_exit_cases

Columns:

- id PK;
- participation_episode_id UNIQUE FK;
- state;
- initiated_at nullable;
- finalized_at nullable;
- transition_support_status nullable;
- unresolved_obligation_count;
- version;
- created_at;
- updated_at.

### exit_reconciliation_items

Columns:

- id PK;
- exit_case_id FK;
- item_type;
- source_reference;
- classification;
- amount nullable;
- asset_quantity nullable;
- status;
- resolution_reference nullable;
- created_at;
- updated_at.

No FINALIZED transition is permitted while required exit reconciliation items remain unresolved.

## 20. Financial Journal Tables

### journal_entries

Append-only after POSTED.

Columns:

- id PK;
- business_event_type;
- business_event_id;
- legal_entity_id FK;
- currency;
- state;
- effective_at;
- posted_at nullable;
- reversal_of_entry_id nullable FK same table;
- idempotency_key;
- actor_reference;
- correlation_id;
- causation_id;
- created_at.

Unique:

- idempotency_key within posting domain;
- a journal entry may have at most one full reversal unless accounting policy explicitly allows chained correction.

### journal_postings

Append-only.

Columns:

- id PK;
- journal_entry_id FK;
- account_code;
- legal_entity_id FK;
- economic_owner_type;
- economic_owner_id nullable;
- participant_id nullable;
- program_id nullable;
- provider_id nullable;
- asset_position_id nullable;
- guarantee_case_id nullable;
- claim_id nullable;
- reserve_account_id nullable;
- debit_amount;
- credit_amount;
- currency;
- created_at.

Checks:

- debit_amount >= 0;
- credit_amount >= 0;
- exactly one of debit_amount / credit_amount should be positive for ordinary monetary posting lines;
- posting currency = journal entry currency unless multi-currency capability is explicitly introduced later.

Critical invariant per posted journal entry:

```
SUM(debit_amount) = SUM(credit_amount)
```

must be validated before transition to POSTED and should be protected by transactional database logic.

### journal_account_taxonomy

Stable product-level account taxonomy.

Columns:

- account_code PK;
- name;
- account_class;
- normal_balance;
- active;
- created_at.

### legal_entity_account_mappings

Columns:

- id PK;
- legal_entity_id FK;
- product_account_code FK;
- external_chart_account_code;
- effective_from;
- effective_to nullable;
- created_at.

This maps Badban product taxonomy to statutory accounting exports.

## 21. Reconciliation Tables

### reconciliation_cases

Columns:

- id PK;
- reconciliation_type;
- internal_entity_type;
- internal_entity_id;
- external_provider_id nullable;
- external_reference nullable;
- status;
- materiality;
- mismatch_reason_code nullable;
- compared_at nullable;
- resolved_at nullable;
- resolution_reference nullable;
- version;
- created_at;
- updated_at.

Indexes:

- (reconciliation_type, status);
- (internal_entity_type, internal_entity_id);
- (external_provider_id, status);
- created_at / compared_at.

### reconciliation_observations

Append-only.

Columns:

- id PK;
- reconciliation_case_id FK;
- internal_value_reference;
- external_value_reference;
- difference_payload;
- evidence_reference nullable;
- observed_at;
- created_at.

Original mismatch evidence is never overwritten.

## 22. Audit Tables

### audit_events

Append-only.

Columns:

- id PK;
- aggregate_type;
- aggregate_id;
- aggregate_version;
- action;
- previous_state nullable;
- new_state nullable;
- actor_type;
- actor_id;
- reason_code nullable;
- policy_pack_id nullable;
- evidence_reference nullable;
- correlation_id;
- causation_id nullable;
- occurred_at;
- created_at.

Indexes:

- (aggregate_type, aggregate_id, aggregate_version);
- actor_id;
- correlation_id;
- occurred_at.

No application-level UPDATE/DELETE permission should exist for ordinary runtime identities.

## 23. Evidence Tables

### evidence_references

Columns:

- id PK;
- evidence_type;
- storage_provider;
- storage_reference;
- external_reference nullable;
- content_hash nullable;
- media_type nullable;
- source_legal_entity_id nullable;
- verified_status;
- captured_at;
- created_at.

The system stores references/metadata, not provider credentials.

If evidence content contains sensitive personal/financial data, access must be separately controlled.

## 24. Transactional Outbox

### outbox_events

Columns:

- id PK;
- event_type;
- aggregate_type;
- aggregate_id;
- aggregate_version;
- payload_reference_or_payload;
- correlation_id;
- causation_id nullable;
- created_at;
- available_at;
- published_at nullable;
- attempt_count;
- last_error_code nullable.

Rules:

- inserted in the same database transaction as the domain state change;
- publisher retries safely;
- published_at set only after confirmed broker/provider handoff according to adapter contract;
- business transaction never waits for remote completion when asynchronous semantics apply.

Indexes:

- (published_at, available_at);
- aggregate ID/version.

## 25. Transactional Inbox / Deduplication

### inbox_messages

Columns:

- id PK;
- source_provider_id nullable;
- message_type;
- external_message_id;
- payload_hash nullable;
- received_at;
- processed_at nullable;
- process_status;
- failure_reason_code nullable;
- correlation_id nullable.

Unique:

```
(source_provider_id, message_type, external_message_id)
```

Rules:

- duplicate inbound events must map to the existing inbox row/business result;
- processing financial effect and marking processed should be transactionally coordinated.

## 26. Idempotency Registry

For synchronous API commands, maintain an idempotency store where needed.

### idempotency_records

Columns:

- id PK;
- scope;
- idempotency_key;
- request_hash;
- business_result_reference nullable;
- response_status;
- created_at;
- expires_at nullable.

Unique:

```
(scope, idempotency_key)
```

If the same key arrives with a different request hash, reject with an idempotency conflict.

## 27. Command Processing / Optimistic Concurrency

Aggregate state-changing persistence must use:

```
UPDATE aggregate
SET ..., version = version + 1
WHERE id = :id
  AND version = :expected_version
```

If affected row count = 0:

- return `AGGREGATE_VERSION_CONFLICT`;
- do not silently overwrite;
- caller/application service may re-read and re-evaluate.

## 28. Capacity Reservation Concurrency

The guarantee reservation transaction must lock or otherwise serialize the relevant capacity rows.

Recommended logical transaction:

```
BEGIN

lock selected asset_capacity_locks rows
read latest eligible valuation references
validate policy pack ACTIVE
validate portfolio risk snapshot
recalculate available capacity
insert/update BackingAllocation
update capacity lock projection
update GuaranteeCase to RESERVED
insert audit event
insert outbox event if needed

COMMIT
```

No remote provider call occurs inside this transaction.

## 29. Guarantee Activation Transaction

Logical transaction:

```
BEGIN

lock GuaranteeCase
lock BackingAllocation
verify state = ISSUED
verify legal guarantee evidence
verify lender disbursement inbox event
verify external principal = issued guarantee
insert/update ExternalLoanMirror
move backing RESERVED → ENCUMBERED
update GuaranteeCase → ACTIVE
write journal if required
write audit event
write outbox event

COMMIT
```

On amount mismatch, transaction rolls back with:

`LOAN_GUARANTEE_AMOUNT_MISMATCH`.

## 30. Repayment Processing Transaction

For each authoritative lender repayment event:

```
BEGIN

deduplicate inbox message
lock ExternalLoanMirror
apply repayment once
update outstanding principal
if DECLINING guarantee:
  lock GuaranteeCase / BackingAllocation
  calculate permitted exposure reduction
  release matching backing
write required journal/audit
mark inbox processed

COMMIT
```

Duplicate message produces no duplicate reduction or release.

## 31. Claim Settlement Transaction

Settlement should atomically coordinate:

- GuaranteeClaim state;
- reserve draw ledger postings;
- settlement reference;
- GuaranteeCase exposure state;
- RecoveryCase creation/opening;
- audit/outbox.

External bank transfer itself is not assumed atomic with database posting.

If payment rail confirmation is asynchronous, use explicit `SETTLEMENT_PENDING` before `PAID`.

## 32. Soft Delete Policy

Financially relevant tables must not use generic `deleted_at` to make historical rows disappear from normal logic.

Use explicit lifecycle states such as:

- RETIRED;
- TERMINATED;
- SUPERSEDED;
- CLOSED;
- REVOKED.

Physical deletion is limited to non-financial temporary data under retention policy.

## 33. Retention and Archival

Retention duration is not fixed by this document.

However:

- journal;
- audit;
- guarantee;
- claim;
- repayment;
- provider evidence;
- reconciliation;
- policy snapshots

must be designed for long-term retention and export without loss of referential integrity.

Archive strategy must preserve immutable IDs and relationships.

## 34. Referential Integrity Rules

Use foreign keys for all internal references where data resides in the same relational store.

Do not use free-text IDs for internal aggregate references.

External references remain text/provider-scoped fields.

Financial journal/audit references to historical business objects should not cascade-delete.

Recommended delete behavior for financial tables:

```
ON DELETE RESTRICT / NO ACTION
```

rather than cascade.

## 35. Enumeration Strategy

Lifecycle states and reason codes should be controlled centrally.

Do not use unconstrained free-text status values.

Implementation may use:

- database enums;
- reference tables;
- constrained text + application enum.

Whichever mechanism is selected must support safe schema evolution and backward compatibility.

## 36. Indexing Baseline

The pilot should index all:

- foreign keys used in joins;
- active state filters;
- external provider identifiers;
- reservation expiry;
- provider event IDs;
- reconciliation status;
- journal business references;
- audit aggregate references;
- outbox unpublished events;
- inbox unprocessed events;
- latest valuation lookup by Asset Position;
- guarantee state/provider/participant queries.

Index design must be validated against real query plans before production.

## 37. Database-Level Invariants vs Application Invariants

### Database-enforced whenever practical

- primary/foreign key integrity;
- uniqueness;
- non-negative numeric constraints;
- advance rate range;
- allocation balance;
- idempotency uniqueness;
- one external loan ID per provider;
- one participation exit case per episode;
- journal posting line validity.

### Application + transaction-enforced

- legal authorization scope;
- policy version eligibility;
- one-to-one guarantee/loan equality across aggregates;
- portfolio risk gate;
- capacity availability across positions;
- valid state transition;
- claim eligible amount against current exposure;
- final exit reconciliation completeness.

### Reconciliation-enforced

- external lender outstanding;
- legal guarantee existence;
- custody quantity;
- legal collateral registry state;
- real cash settlement.

## 38. Read Models

Operational UI and reporting should not directly reconstruct complex screens from normalized write tables on every request.

Create derived read models/projections for:

- participant financial summary;
- Asset Position + valuation summary;
- available guarantee capacity;
- guarantee workspace;
- external loan status;
- risk dashboard;
- reconciliation queue;
- claim/recovery workspace;
- participant exit statement.

Read models are disposable/rebuildable projections.

They are not authoritative sources for financial transitions.

## 39. Schema Migration Rule

All schema changes must be migration-controlled.

Migration policy must support:

- forward migration;
- safe rollback where possible;
- data backfill with auditability;
- compatibility during staged deployment;
- no destructive change to historical financial records without explicit migration approval.

## 40. Technical Consequences

This model creates four distinct persistence categories:

1. **mutable aggregate state** — current operational state with optimistic versioning;
2. **append-only historical truth** — journal, audit, valuation, provider events, reconciliation observations;
3. **integration reliability state** — outbox, inbox, idempotency;
4. **derived projections** — read models and capacity/risk views.

The next Technical document should define the detailed ledger account taxonomy and posting templates for guarantee reservation/activation, return allocation, claim settlement, recovery, reserve draw/replenishment, and participant exit.
