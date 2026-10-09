from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from badban.application.idempotency import canonical_request_hash
from badban.application.lender_adapter import LenderReconciliationLoan

type SourceType = Literal[
    "LENDER", "GUARANTEE_ISSUER", "CUSTODY", "SETTLEMENT", "COLLATERAL_REGISTRY", "LEDGER"
]
type Text = Annotated[str, Field(min_length=1, max_length=500, pattern=r".*\S.*")]
type Amount = Annotated[str, Field(pattern=r"^\d{1,20}(?:\.\d{1,18})?$", max_length=40)]
type Balance = Annotated[str, Field(pattern=r"^-?\d{1,60}(?:\.\d{1,18})?$", max_length=80)]


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceTarget(CanonicalModel):
    reconciliation_type: SourceType
    provider_id: UUID | None = None
    source_legal_entity_id: UUID | None = None
    program_id: UUID | None = None

    @model_validator(mode="after")
    def identity_shape(self) -> SourceTarget:
        supplied = (
            self.provider_id is not None,
            self.source_legal_entity_id is not None,
            self.program_id is not None,
        )
        expected = (
            (True, False, False)
            if self.reconciliation_type == "LENDER"
            else (
                (False, False, True)
                if self.reconciliation_type == "LEDGER"
                else (False, True, False)
            )
        )
        if supplied != expected:
            raise ValueError("exactly the authoritative target identity is required")
        return self

    @property
    def identity(self) -> UUID:
        identity = self.provider_id or self.source_legal_entity_id or self.program_id
        assert identity is not None
        return identity


class Record(CanonicalModel):
    observed_at: AwareDatetime


class LenderRecord(Record):
    external_loan_id: str = Field(min_length=1, max_length=255)
    original_principal: str = Field(pattern=r"^\d+(?:\.\d+)?$", max_length=80)
    outstanding_principal: str = Field(pattern=r"^\d+(?:\.\d+)?$", max_length=80)
    currency: str = Field(min_length=1, max_length=16)
    state: Literal["PENDING", "ACTIVE", "DELINQUENT", "SETTLED", "REPLACED"]

    @model_validator(mode="after")
    def lender_contract(self) -> LenderRecord:
        LenderReconciliationLoan(
            external_loan_id=self.external_loan_id,
            original_principal=self.original_principal,
            outstanding_principal=self.outstanding_principal,
            currency=self.currency,
            provider_state=self.state,
            observed_at=self.observed_at,
        )
        return self


class IssuerRecord(Record):
    external_guarantee_id: Text
    issued_amount: Amount
    issued_at: AwareDatetime
    beneficiary: UUID
    state: Text
    currency: Text | None = None


class CustodyRecord(Record):
    asset_position_id: UUID
    custody_reference: Text
    asset_type: Text
    quantity: Amount
    unit_code: Text
    state: Text
    ownership_reference: Text | None = None
    control_reference: Text | None = None
    restriction_state: Text | None = None
    release_realization_state: Text | None = None


class SettlementRecord(Record):
    settlement_reference: Text
    amount: Amount
    currency: Text
    payer_role: Text
    payee_role: Text
    value_date: AwareDatetime
    state: Text
    reversal_reference: Text | None = None
    correction_reference: Text | None = None


class RegistryRecord(Record):
    registration_id: Text
    state: Text
    collateral_reference: Text
    secured_amount: Amount | None = None
    release_enforcement_state: Text | None = None


class LedgerRecord(Record):
    account_code: Text
    currency: Text
    economic_owner_type: Text
    economic_owner_id: UUID | None
    participant_id: UUID | None
    program_id: UUID
    provider_id: UUID | None
    asset_position_id: UUID | None
    guarantee_case_id: UUID | None
    claim_id: UUID | None
    reserve_account_id: UUID | None
    ledger_layer: Literal["MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"]
    normal_balance: Literal["DEBIT", "CREDIT", "MEMO"]
    balance: Balance


class Snapshot(CanonicalModel):
    source_id: UUID
    scope_definition: dict[str, str]
    snapshot_at: AwareDatetime
    received_at: AwareDatetime
    source_reference: Text
    schema_version: Literal["reconciliation-source-v1"]
    contract_version: Text
    mapping_version: Text
    normalization_version: Text | None = None
    evidence_references: tuple[Text, ...] = Field(min_length=1, max_length=1000)
    coverage_from: AwareDatetime | None = None
    coverage_to: AwareDatetime | None = None
    watermark: Text | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    def semantic_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"received_at", "content_hash"})

    @model_validator(mode="after")
    def integrity(self) -> Snapshot:
        if self.content_hash != canonical_request_hash(self.semantic_payload()):
            raise ValueError("snapshot content hash disagrees with canonical content")
        if (self.coverage_from is None) != (self.coverage_to is None):
            raise ValueError("coverage needs both interval endpoints")
        if self.coverage_from is not None and self.coverage_to is not None:
            if self.coverage_from > self.coverage_to or self.coverage_to > self.snapshot_at:
                raise ValueError("invalid coverage interval")
        return self


class LenderSnapshot(Snapshot):
    reconciliation_type: Literal["LENDER"]
    records: tuple[LenderRecord, ...] = Field(max_length=10000)


class IssuerSnapshot(Snapshot):
    reconciliation_type: Literal["GUARANTEE_ISSUER"]
    records: tuple[IssuerRecord, ...] = Field(max_length=10000)


class CustodySnapshot(Snapshot):
    reconciliation_type: Literal["CUSTODY"]
    records: tuple[CustodyRecord, ...] = Field(max_length=10000)


class SettlementSnapshot(Snapshot):
    reconciliation_type: Literal["SETTLEMENT"]
    records: tuple[SettlementRecord, ...] = Field(max_length=10000)


class RegistrySnapshot(Snapshot):
    reconciliation_type: Literal["COLLATERAL_REGISTRY"]
    records: tuple[RegistryRecord, ...] = Field(max_length=10000)


class LedgerSnapshot(Snapshot):
    reconciliation_type: Literal["LEDGER"]
    records: tuple[LedgerRecord, ...] = Field(max_length=10000)


type CanonicalSnapshot = Annotated[
    LenderSnapshot
    | IssuerSnapshot
    | CustodySnapshot
    | SettlementSnapshot
    | RegistrySnapshot
    | LedgerSnapshot,
    Field(discriminator="reconciliation_type"),
]
SNAPSHOT_ADAPTER: TypeAdapter[CanonicalSnapshot] = TypeAdapter(CanonicalSnapshot)


@dataclass(frozen=True)
class SourceCapability:
    source_id: UUID
    reconciliation_type: SourceType
    contract_version: str
    mapping_version: str
    schema_version: str = "reconciliation-source-v1"
    normalization_version: str | None = None


class ReconciliationSourceUnavailable(RuntimeError):
    def __init__(
        self,
        code: Literal[
            "SOURCE_UNAVAILABLE", "SOURCE_TIMEOUT", "SOURCE_TRANSPORT_ERROR"
        ] = "SOURCE_UNAVAILABLE",
    ) -> None:
        super().__init__(code)
        self.code = code


class ReconciliationSourcePort(Protocol):
    def capability(self) -> SourceCapability: ...

    async def fetch_reconciliation_snapshot(
        self, target: SourceTarget, scope: dict[str, str]
    ) -> CanonicalSnapshot: ...


class ReconciliationSourceRegistry:
    def __init__(self) -> None:
        self._ports: dict[tuple[str, UUID], ReconciliationSourcePort] = {}

    def register(self, port: ReconciliationSourcePort) -> None:
        capability = port.capability()
        key = (capability.reconciliation_type, capability.source_id)
        if key in self._ports:
            raise ValueError("source implementation already registered")
        self._ports[key] = port

    def resolve(self, target: SourceTarget) -> ReconciliationSourcePort:
        try:
            return self._ports[(target.reconciliation_type, target.identity)]
        except KeyError as exc:
            raise ReconciliationSourceUnavailable() from exc


def stable_key(record: Record) -> str:
    if isinstance(record, LenderRecord):
        return record.external_loan_id
    if isinstance(record, IssuerRecord):
        return record.external_guarantee_id
    if isinstance(record, CustodyRecord):
        return canonical_request_hash([str(record.asset_position_id), record.custody_reference])
    if isinstance(record, SettlementRecord):
        return record.settlement_reference
    if isinstance(record, RegistryRecord):
        return record.registration_id
    if isinstance(record, LedgerRecord):
        return canonical_request_hash(
            record.model_dump(mode="json", exclude={"balance", "observed_at"})
        )
    raise ValueError("unsupported canonical record")


def canonical_fields(record: Record) -> dict[str, str]:
    return {
        key: ("null" if value is None else str(value))
        for key, value in record.model_dump(mode="json").items()
        if (value is not None or isinstance(record, LedgerRecord)) and key != "observed_at"
    }


def verify_source_snapshot(
    *,
    target: SourceTarget,
    scope: dict[str, str],
    capability: SourceCapability,
    snapshot: CanonicalSnapshot,
) -> CanonicalSnapshot:
    """Check source provenance before any policy comparison or persistence.

    Identity, scope, evidence, schema, mapping and contract versions must all
    match. Revalidating catches Pydantic model_copy bypasses. This boundary
    deliberately does NOT decide freshness, matching or financial eligibility.
    """
    if capability.source_id != target.identity or capability.reconciliation_type != (
        target.reconciliation_type
    ):
        raise ValueError("source capability does not match authorized target")

    checked = SNAPSHOT_ADAPTER.validate_python(snapshot.model_dump(mode="json"))
    if checked.reconciliation_type != target.reconciliation_type:
        raise ValueError("snapshot type does not match authorized target")
    if checked.source_id != capability.source_id:
        raise ValueError("snapshot source does not match capability")
    if checked.scope_definition != scope:
        raise ValueError("snapshot scope does not match authorized scope")
    if (
        checked.schema_version != capability.schema_version
        or checked.contract_version != capability.contract_version
        or checked.mapping_version != capability.mapping_version
        or checked.normalization_version != capability.normalization_version
    ):
        raise ValueError("snapshot versions do not match registered source")
    if checked.snapshot_at > checked.received_at:
        raise ValueError("source snapshot time is later than receipt time")
    if any(record.observed_at > checked.snapshot_at for record in checked.records):
        raise ValueError("record observation is later than source snapshot")
    return checked
