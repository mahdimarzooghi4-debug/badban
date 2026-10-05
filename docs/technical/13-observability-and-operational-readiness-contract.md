# Badban Observability and Operational Readiness Contract

- **Status:** Proposed
- **Date:** 2026-10-05
- **Stage:** Technical
- **Scope:** bounded external-lender pilot
- **Depends on:** Technical Foundation; Event Contracts; Provider Adapter Contracts; Reconciliation Contract; Security Contract

## 1. Objective

Define how Badban detects operational failure, financial-control failure, provider degradation, security anomalies, and backlog/staleness before they become unsafe business outcomes.

Core rule:

```
Operational health != business correctness
```

A healthy process or HTTP endpoint does not prove that guarantees, reconciliations, ledgers, providers, or policy state are correct.

## 2. Telemetry Pillars

Badban must provide:

- structured logs;
- metrics;
- distributed traces;
- audit events;
- business-control indicators;
- health/readiness signals.

Audit events remain separate from ordinary logs.

## 3. Correlation

All critical requests/workflows should propagate:

- correlation_id;
- causation_id where applicable;
- aggregate/business entity ID;
- provider ID when relevant;
- operation ID;
- trace ID.

A production incident must be traceable from API request through domain command, journal/event, provider operation, and reconciliation outcome.

## 4. Structured Logging

Logs should be structured and machine-queryable.

Recommended fields:

- timestamp;
- environment;
- service/component;
- severity;
- correlation_id;
- trace_id;
- actor/service identity;
- aggregate type/id;
- provider id;
- event/command name;
- reason/error code;
- latency;
- outcome.

Secrets, tokens, private keys, full evidence payloads, and unnecessary PII must never be logged.

## 5. Metrics Categories

### API

- request count;
- success/failure;
- p50/p95/p99 latency;
- 4xx/5xx rate;
- domain rejection rate by reason code;
- idempotency conflicts;
- version conflicts.

### Domain / Financial Controls

- guarantee requests/reservations/activations;
- blocked reservations;
- stale valuation blocks;
- portfolio RED blocks;
- one-to-one mismatch count;
- ledger posting failures;
- unbalanced journal attempts;
- claim approvals/payments;
- recovery open age;
- unresolved exit blockers.

### Integration

- provider request success/failure;
- timeout/retry count;
- UNKNOWN_OUTCOME count;
- circuit-breaker state;
- inbound event lag;
- outbox backlog;
- inbox backlog;
- dead-letter count;
- contract mismatch count.

### Reconciliation

- run success/failure;
- lag by provider/type;
- mismatch counts by materiality;
- oldest unresolved CRITICAL;
- active reconciliation blocks;
- stale-source count;
- mean time to resolution.

### Security

- authentication failures;
- authorization denials;
- signature failures;
- replay detections;
- secret retrieval failures;
- break-glass use;
- privileged-role changes.

## 6. Business-Control Indicators

The following are first-class operational indicators, not generic infrastructure metrics:

- count of guarantees in RESERVED beyond expected age;
- ISSUED but not ACTIVE beyond expected age;
- ACTIVE guarantees lacking fresh lender reconciliation;
- external loans with no recent provider sync;
- open claims past expected review/settlement stage;
- recovery cases past expected age;
- stale valuations used only in historical state but blocking new capacity;
- unresolved CRITICAL reconciliation cases;
- active provider authorization nearing expiry;
- Policy Pack nearing expiry/retirement where applicable;
- participant exit cases blocked by unresolved obligations.

Exact thresholds are versioned operational policy.

## 7. Health vs Readiness

### Liveness

Answers:

> Is the process alive?

Liveness must not depend on external providers.

### Readiness

Answers:

> Can this instance safely receive its intended traffic?

Readiness may require:

- database connectivity;
- required internal dependencies;
- secret availability;
- broker connectivity where required for safe command processing.

### Business Readiness

Separate endpoint/view answers:

> Is Badban safe to execute new high-impact financial actions?

Business readiness may be false when:

- provider unavailable;
- reconciliation stale;
- risk RED;
- policy inactive;
- legal authorization invalid;
- reserve hard gate breached.

Infrastructure readiness must not disguise business unavailability.

## 8. Provider Health

Each provider has status:

- AVAILABLE;
- DEGRADED;
- UNAVAILABLE;
- AUTH_FAILURE;
- CONTRACT_MISMATCH.

Provider health includes:

- last successful command;
- last successful inbound event;
- last reconciliation snapshot;
- current circuit state;
- auth state;
- lag.

Provider health never rewrites existing financial state.

## 9. SLI Categories

SLIs should be defined for:

- API availability;
- command latency;
- read-model freshness;
- event publication lag;
- inbox processing lag;
- provider synchronization lag;
- reconciliation freshness;
- critical financial workflow completion;
- backup success;
- restore verification.

## 10. SLO Governance

Exact numeric SLO targets are not invented in Technical documentation unless approved.

Before production, Release governance must approve concrete targets for the pilot.

SLOs should distinguish:

- customer-facing availability;
- internal operational availability;
- financial-control freshness;
- provider-dependent service quality.

## 11. Error Budget Rule

If formal SLO/error budgets are used, they must not permit spending error budget on violations of hard financial/legal invariants.

Examples that are not acceptable "budgeted" failures:

- duplicate financial posting;
- guarantee/loan principal mismatch;
- unauthorized transaction;
- corrupted journal;
- bypassed maker-checker;
- untracked claim settlement.

## 12. Alert Classes

### P1 / Critical

Examples:

- ledger integrity failure;
- one-to-one principal mismatch on attempted activation;
- unauthorized high-impact action;
- CRITICAL reconciliation mismatch affecting active exposure;
- production secret compromise;
- widespread provider contract mismatch;
- data corruption.

### P2 / High

Examples:

- provider unavailable beyond policy window;
- outbox/inbox backlog threatening freshness;
- repeated settlement mismatch;
- stale reconciliation blocking operations;
- reserve/risk hard warning approaching breach.

### P3 / Warning

Examples:

- increasing retry rate;
- expiring certificate/authorization;
- read-model lag;
- non-critical provider degradation.

Severity thresholds are operational policy.

## 13. Alert Quality

Alerts must be actionable.

Each alert should identify:

- symptom;
- affected component/provider;
- business impact;
- correlation/reference;
- first-seen time;
- current duration;
- suggested runbook.

Avoid alerting solely on noisy low-level metrics without business impact.

## 14. Runbooks

Required runbooks include at least:

- provider outage;
- provider UNKNOWN_OUTCOME;
- webhook authentication/signature failure;
- outbox backlog;
- inbox processing failure;
- event sequence gap;
- stale valuation source;
- critical reconciliation mismatch;
- ledger posting failure;
- database degradation;
- secret/certificate expiry;
- credential compromise;
- failed backup;
- failed restore verification;
- risk RED / issuance stop;
- policy activation failure.

Runbooks must state what operators may and may not change manually.

## 15. Financial Incident Rule

During a financial-control incident, operators must prefer:

```
stop unsafe new actions
→ preserve evidence
→ reconcile
→ correct through domain command/reversal
→ verify
→ resume
```

Never "repair" a production incident by directly editing ledger/history rows.

## 16. Dashboards

Minimum dashboards:

### Executive / Pilot Health

- active participants;
- active guarantees;
- blocked transactions;
- provider health;
- CRITICAL reconciliation count;
- risk state;
- major incidents.

### Operations

- work queues;
- stuck lifecycle states;
- integration pending/unknown outcomes;
- reconciliation cases;
- provider freshness.

### Finance / Control

- journal posting health;
- reserve metrics;
- claims/recovery;
- ledger/sub-ledger reconciliation;
- settlement exceptions.

### Security

- auth failures;
- privileged changes;
- provider signature failures;
- secret/key/certificate status;
- break-glass events.

## 17. Tracing

Distributed traces should cover:

- API command;
- domain transaction;
- outbox publication;
- integration worker;
- provider call;
- inbound callback/inbox;
- reconciliation;
- journal posting.

Trace sampling must never expose restricted payloads.

High-impact failures should retain enough trace context for investigation.

## 18. Read Model Freshness

Every derived read model should expose or internally track:

- source aggregate version;
- projection version;
- last update timestamp;
- lag.

UI must not present stale operational projections as real-time authoritative state when freshness is material.

## 19. Outbox / Inbox Monitoring

Monitor:

- oldest unpublished outbox event;
- unpublished count;
- publish failure rate;
- oldest unprocessed inbox message;
- processing failure rate;
- dead-letter count;
- duplicate-event rate.

Backlog age is usually more meaningful than queue length alone.

## 20. Capacity and Risk Monitoring

Monitor:

- available guarantee capacity;
- reserved capacity;
- active exposure;
- concentration utilization;
- reserve coverage;
- GREEN/AMBER/RED state;
- number of blocked issuance attempts.

Metrics are read models/control indicators, not substitutes for authoritative calculation.

## 21. Reconciliation Monitoring

Monitor by provider/type:

- freshness;
- last successful run;
- unresolved mismatch count;
- CRITICAL count;
- active blocks;
- recurrence rate;
- oldest unresolved case.

A "successful job" with CRITICAL mismatches is not a healthy reconciliation outcome.

## 22. Security Monitoring

Security events must be distinguishable from application errors.

Monitor:

- repeated failed authentication;
- role/grant changes;
- self-approval attempts;
- authorization denials on high-impact commands;
- webhook signature failures;
- replay attempts;
- break-glass access;
- secret retrieval failures;
- certificate/key expiry.

## 23. Audit vs Operational Logs

Audit records answer:

> Who did what, to which business object, under which policy/approval?

Operational logs answer:

> What did the software do while processing it?

Neither replaces the other.

## 24. Retention

Telemetry retention periods are not fixed here.

However:

- audit retention follows legal/accounting requirements;
- logs/traces should retain enough history for incident investigation;
- security events may require longer retention than ordinary debug telemetry.

Retention policy must balance investigation needs with data minimization.

## 25. Incident Lifecycle

Recommended incident lifecycle:

```
DETECTED
→ TRIAGED
→ CONTAINED
→ MITIGATED
→ RECOVERED
→ VERIFIED
→ REVIEWED
→ CLOSED
```

Financial incidents require reconciliation/integrity verification before RECOVERED/VERIFIED.

## 26. Incident Evidence

Incident records should retain:

- incident ID;
- severity;
- start/end times;
- affected services/providers;
- affected business entities if known;
- customer/business impact;
- commands/actions taken;
- privileged access used;
- related audit/reconciliation references;
- root cause;
- remediation.

## 27. Post-Incident Review

P1/P2 incidents affecting financial integrity, provider trust, reconciliation, security, or production data require post-incident review.

Review should identify:

- root cause;
- detection gap;
- control failure;
- recovery effectiveness;
- required code/config/policy/runbook changes;
- regression tests.

## 28. Operational Readiness Checklist

Before Stage/real-money pilot, verify:

- dashboards available;
- alerts configured;
- runbooks written;
- on-call/escalation ownership defined;
- provider contacts defined;
- backup monitoring active;
- restore rehearsal completed;
- reconciliation monitoring active;
- security alerting active;
- dead-letter/replay procedures tested;
- business stop controls tested.

## 29. Stop Controls

Operations must have explicit safe controls to:

- stop new guarantee reservations;
- stop activation;
- suspend a provider;
- suspend an Asset Type for new transactions;
- prevent claim settlement;
- prevent collateral release.

Stop controls are restrictive only and must not modify existing obligations.

Every activation/deactivation is audited.

## 30. Recovery Verification

After outage/recovery:

1. verify database integrity;
2. verify outbox/inbox backlog;
3. process/reconcile provider state;
4. verify ledger/sub-ledger consistency;
5. verify reconciliation freshness;
6. verify policy/provider/legal status;
7. clear business blocks only after evidence.

"Service is up" is not enough.

## 31. Backup and Restore Readiness

Monitor:

- backup success/failure;
- backup age;
- encryption/integrity status;
- restore rehearsal date/result.

Restore rehearsal must verify:

- application starts;
- journal balances;
- aggregate versions;
- outbox/inbox integrity;
- reconciliation ability;
- evidence references;
- access-control integrity.

## 32. Capacity Planning

Monitor:

- database storage/growth;
- connection saturation;
- worker backlog;
- provider-rate limits;
- event throughput;
- reconciliation batch duration;
- evidence storage growth.

Pilot design prioritizes correctness over premature horizontal complexity.

## 33. Performance Observability

Track performance separately for:

- read queries;
- state-changing commands;
- financial posting transactions;
- reconciliation jobs;
- provider calls;
- projection rebuilds.

A slow but correct financial command is different from an unsafe timed-out provider operation.

## 34. Operational Change Tracking

Deployments/config changes should be visible in telemetry timelines.

Record:

- source commit;
- artifact version/digest;
- deployment ID;
- config version;
- policy activation events;
- provider mapping version changes.

This supports causality analysis.

## 35. Test Contract

Operational readiness tests must include:

- forced provider outage;
- provider timeout/UNKNOWN_OUTCOME;
- outbox publisher failure/recovery;
- inbox worker crash/replay;
- reconciliation stale/block behavior;
- database fail/restart where supported;
- invalid secret/certificate;
- alert firing;
- stop-control activation;
- backup restore rehearsal;
- post-recovery integrity checks.

## 36. Hard Invariants

1. Infrastructure health is never treated as proof of financial correctness.
2. Business readiness is evaluated separately from liveness/readiness.
3. Critical financial/control failures generate actionable alerts.
4. Logs never become authoritative financial state.
5. CRITICAL reconciliation mismatches remain visible until resolved.
6. Provider unavailability never becomes inferred success.
7. Recovery requires integrity/reconciliation verification.
8. Operators repair financial state only through domain/reversal workflows.
9. Stop controls restrict new actions without rewriting existing obligations.
10. Observability must correlate technical events to business entities without leaking secrets/PII.

## 37. Next Technical Contracts

Next:

1. Deployment / Runtime Topology and Non-Functional Requirements;
2. Technical Stage Completion Review.
