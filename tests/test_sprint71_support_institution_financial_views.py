from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from badban.api.app import create_app
from badban.application.journal import JournalLine, post_journal
from badban.config import Settings
from badban.infrastructure.persistence.models import (
    Identity,
    LegalEntity,
    Participant,
    Program,
    RoleGrant,
)
from badban.security.authorization import ROLE_SUPPORT_INSTITUTION_OPERATOR

SOURCE = "/api/v1/support-institution/programs"


class FakeVerifier:
    async def verify(self, token: str) -> dict[str, str]:
        return {"sub": token}


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    app.state.token_verifier = FakeVerifier()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _headers(subject: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {subject}"}


async def _seed(database) -> dict[str, object]:
    now = datetime.now(UTC)
    operator = Identity(
        identity_type="STAFF",
        external_subject=f"sprint71-operator-{uuid4()}",
        status="ACTIVE",
    )
    outsider = Identity(
        identity_type="STAFF",
        external_subject=f"sprint71-outsider-{uuid4()}",
        status="ACTIVE",
    )
    entity = LegalEntity(
        legal_name="Sprint 71 Supporting Entity",
        registration_identifier=f"SPRINT71-ENTITY-{uuid4()}",
        entity_type="TEST",
        status="ACTIVE",
        created_by=operator.id,
        version=1,
    )
    program = Program(
        code=f"SPRINT71-{uuid4()}",
        name="Sprint 71 Authorized Program",
        status="ACTIVE",
        legal_entity_id=entity.id,
        created_by=operator.id,
        version=1,
    )
    other_program = Program(
        code=f"SPRINT71-OTHER-{uuid4()}",
        name="Sprint 71 Other Program",
        status="ACTIVE",
        legal_entity_id=entity.id,
        created_by=operator.id,
        version=1,
    )
    participant_a = Participant(
        external_reference=f"sprint71-participant-a-{uuid4()}",
        lifecycle_status="ACTIVE",
    )
    participant_b = Participant(
        external_reference=f"sprint71-participant-b-{uuid4()}",
        lifecycle_status="ACTIVE",
    )
    async with database.session_factory() as session:
        async with session.begin():
            session.add_all(
                [operator, outsider, entity, program, other_program, participant_a, participant_b]
            )
            await session.flush()
            session.add_all(
                [
                    RoleGrant(
                        identity_id=operator.id,
                        role_code=ROLE_SUPPORT_INSTITUTION_OPERATOR,
                        scope_type="PROGRAM",
                        scope_id=program.id,
                        valid_from=now - timedelta(minutes=5),
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=operator.id,
                        reason_ref="sprint71-authorized-program",
                        version=1,
                    ),
                    RoleGrant(
                        identity_id=outsider.id,
                        role_code=ROLE_SUPPORT_INSTITUTION_OPERATOR,
                        scope_type="PROGRAM",
                        scope_id=other_program.id,
                        valid_from=now - timedelta(minutes=5),
                        valid_until=None,
                        status="ACTIVE",
                        granted_by=operator.id,
                        reason_ref="sprint71-other-program-only",
                        version=1,
                    ),
                ]
            )
    return {
        "operator": operator,
        "outsider": outsider,
        "entity": entity,
        "program": program,
        "other_program": other_program,
        "participant_a": participant_a,
        "participant_b": participant_b,
    }


async def _post_program_entry(
    database,
    seeded: dict[str, object],
    *,
    amount: str = "100",
    currency: str = "IRR",
    participant_id=None,
    event_type: str = "SPRINT71_INTERNAL_POSTING",
) -> str:
    operator = seeded["operator"]
    entity = seeded["entity"]
    program = seeded["program"]
    assert isinstance(operator, Identity)
    assert isinstance(entity, LegalEntity)
    assert isinstance(program, Program)
    value = Decimal(amount)
    if participant_id is None:
        credit_line = JournalLine(
            account_code="2030.PROGRAM_CAPITAL_BALANCE",
            economic_owner_type="PROGRAM",
            program_id=program.id,
            credit_amount=value,
        )
    else:
        credit_line = JournalLine(
            account_code="2000.PARTICIPANT_PAYABLE_BALANCE",
            economic_owner_type="PARTICIPANT",
            economic_owner_id=participant_id,
            participant_id=participant_id,
            program_id=program.id,
            credit_amount=value,
        )
    key = f"sprint71-{uuid4()}"
    async with database.session_factory() as session:
        async with session.begin():
            await post_journal(
                session,
                business_event_type=event_type,
                business_event_id=f"private-event-id-{uuid4()}",
                legal_entity_id=entity.id,
                currency=currency,
                idempotency_key=key,
                actor_reference=operator.id,
                actor_type="STAFF",
                correlation_id=uuid4(),
                evidence_reference="evidence:sprint71-test",
                settlement_reference="PRIVATE_SETTLEMENT_REFERENCE_SHOULD_NOT_LEAK",
                reason="PRIVATE_REASON_SHOULD_NOT_LEAK",
                lines=[
                    JournalLine(
                        account_code="1000.SETTLEMENT_CASH_CONTROL",
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        debit_amount=value,
                    ),
                    credit_line,
                ],
            )
    return key


async def _post_memo_entry(database, seeded: dict[str, object], *, external: bool) -> None:
    operator = seeded["operator"]
    entity = seeded["entity"]
    program = seeded["program"]
    assert isinstance(operator, Identity)
    assert isinstance(entity, LegalEntity)
    assert isinstance(program, Program)
    if external:
        debit_code = "9050.EXTERNAL_LOAN_PRINCIPAL_MIRROR_MEMO"
        credit_code = "9060.EXTERNAL_LOAN_OUTSTANDING_MIRROR_MEMO"
        event_type = "SPRINT71_EXTERNAL_MIRROR_TEST"
    else:
        debit_code = "9000.GUARANTEE_CAPACITY_RESERVED_MEMO"
        credit_code = "9010.ACTIVE_GUARANTEE_EXPOSURE_MEMO"
        event_type = "SPRINT71_MEMORANDUM_TEST"
    value = Decimal("7")
    async with database.session_factory() as session:
        async with session.begin():
            await post_journal(
                session,
                business_event_type=event_type,
                business_event_id=f"{event_type}-{uuid4()}",
                legal_entity_id=entity.id,
                currency="IRR",
                idempotency_key=f"sprint71-memo-{uuid4()}",
                actor_reference=operator.id,
                actor_type="STAFF",
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code=debit_code,
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        debit_amount=value,
                    ),
                    JournalLine(
                        account_code=credit_code,
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        credit_amount=value,
                    ),
                ],
            )


async def _post_mixed_scope_entry(database, seeded: dict[str, object]) -> None:
    operator = seeded["operator"]
    entity = seeded["entity"]
    program = seeded["program"]
    assert isinstance(operator, Identity)
    assert isinstance(entity, LegalEntity)
    assert isinstance(program, Program)
    value = Decimal("9")
    async with database.session_factory() as session:
        async with session.begin():
            await post_journal(
                session,
                business_event_type="SPRINT71_MIXED_SCOPE_TEST",
                business_event_id=f"mixed-{uuid4()}",
                legal_entity_id=entity.id,
                currency="IRR",
                idempotency_key=f"sprint71-mixed-{uuid4()}",
                actor_reference=operator.id,
                actor_type="STAFF",
                correlation_id=uuid4(),
                lines=[
                    JournalLine(
                        account_code="1000.SETTLEMENT_CASH_CONTROL",
                        economic_owner_type="PROGRAM",
                        program_id=program.id,
                        debit_amount=value,
                    ),
                    JournalLine(
                        account_code="2030.PROGRAM_CAPITAL_BALANCE",
                        economic_owner_type="CORPORATE",
                        program_id=None,
                        credit_amount=value,
                    ),
                ],
            )


@pytest.mark.integration
async def test_financial_history_is_program_scoped_complete_and_paginated(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    seeded = await _seed(database)
    await _post_program_entry(database, seeded, amount="100")
    await _post_program_entry(database, seeded, amount="25")
    await _post_mixed_scope_entry(database, seeded)
    program = seeded["program"]
    operator = seeded["operator"]
    assert isinstance(program, Program)
    assert isinstance(operator, Identity)

    async with await _client(settings) as client:
        first = await client.get(
            f"{SOURCE}/{program.id}/financial-history?limit=1&offset=0",
            headers=_headers(operator.external_subject),
        )
        second = await client.get(
            f"{SOURCE}/{program.id}/financial-history?limit=1&offset=1",
            headers=_headers(operator.external_subject),
        )

    assert first.status_code == 200
    assert second.status_code == 200
    first_data, second_data = first.json(), second.json()
    assert first_data["total_entries"] == 2
    assert second_data["total_entries"] == 2
    assert len(first_data["items"]) == len(second_data["items"]) == 1
    assert first_data["items"][0]["id"] != second_data["items"][0]["id"]
    assert all(item["state"] == "POSTED" for item in first_data["items"] + second_data["items"])
    assert all(
        posting["currency"] == entry["currency"]
        for page in (first_data, second_data)
        for entry in page["items"]
        for posting in entry["postings"]
    )
    payload = str(first_data) + str(second_data)
    assert "PRIVATE_REASON_SHOULD_NOT_LEAK" not in payload
    assert "PRIVATE_SETTLEMENT_REFERENCE_SHOULD_NOT_LEAK" not in payload
    assert "private-event-id" not in payload
    assert "actor_reference" not in payload
    assert "participant_id" not in payload
    assert "economic_owner_id" not in payload
    assert first_data["source_type"] == "INTERNAL_BADBAN_POSTED_JOURNAL"


@pytest.mark.integration
async def test_program_statement_aggregates_owner_class_and_keeps_privacy_and_layers(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    seeded = await _seed(database)
    participant_a = seeded["participant_a"]
    participant_b = seeded["participant_b"]
    operator = seeded["operator"]
    program = seeded["program"]
    assert isinstance(participant_a, Participant)
    assert isinstance(participant_b, Participant)
    assert isinstance(operator, Identity)
    assert isinstance(program, Program)
    await _post_program_entry(database, seeded, amount="10", participant_id=participant_a.id)
    await _post_program_entry(database, seeded, amount="15", participant_id=participant_b.id)
    await _post_program_entry(database, seeded, amount="20", currency="EUR")
    await _post_memo_entry(database, seeded, external=False)
    await _post_memo_entry(database, seeded, external=True)

    async with await _client(settings) as client:
        response = await client.get(
            f"{SOURCE}/{program.id}/financial-statement?limit=100&offset=0",
            headers=_headers(operator.external_subject),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "INTERNAL_BADBAN_POSTED_JOURNAL"
    assert data["program_id"] == str(program.id)
    entity = seeded["entity"]
    assert isinstance(entity, LegalEntity)
    assert data["legal_entity_id"] == str(entity.id)
    assert len(data["content_hash"]) == 64
    assert data["evidence_references"]
    participant_row = next(
        row
        for row in data["items"]
        if row["account_code"] == "2000.PARTICIPANT_PAYABLE_BALANCE"
        and row["currency"] == "IRR"
        and row["economic_owner_type"] == "PARTICIPANT"
    )
    assert participant_row["balance"] == "25.000000000000000000"
    assert {"IRR", "EUR"} <= {row["currency"] for row in data["items"]}
    assert {"MONETARY", "MEMORANDUM_CONTROL", "EXTERNAL_MIRROR"} <= {
        row["ledger_layer"] for row in data["items"]
    }
    assert all(
        "participant_id" not in row and "economic_owner_id" not in row for row in data["items"]
    )
    assert "PRIVATE_REASON_SHOULD_NOT_LEAK" not in str(data)
    assert "PRIVATE_SETTLEMENT_REFERENCE_SHOULD_NOT_LEAK" not in str(data)


@pytest.mark.integration
async def test_mixed_scope_journal_makes_statement_fail_closed(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    seeded = await _seed(database)
    await _post_mixed_scope_entry(database, seeded)
    program = seeded["program"]
    operator = seeded["operator"]
    assert isinstance(program, Program)
    assert isinstance(operator, Identity)

    async with await _client(settings) as client:
        response = await client.get(
            f"{SOURCE}/{program.id}/financial-statement",
            headers=_headers(operator.external_subject),
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_CONTRACT_INVALID"


@pytest.mark.integration
async def test_missing_posted_evidence_is_unavailable_not_zero_and_program_grant_is_exact(
    settings: Settings,
    database,
    clean_sprint07_guarantee_tables,
) -> None:
    seeded = await _seed(database)
    program = seeded["program"]
    outsider = seeded["outsider"]
    operator = seeded["operator"]
    assert isinstance(program, Program)
    assert isinstance(outsider, Identity)
    assert isinstance(operator, Identity)

    async with await _client(settings) as client:
        history = await client.get(
            f"{SOURCE}/{program.id}/financial-history",
            headers=_headers(operator.external_subject),
        )
        statement = await client.get(
            f"{SOURCE}/{program.id}/financial-statement",
            headers=_headers(operator.external_subject),
        )
        denied = await client.get(
            f"{SOURCE}/{program.id}/financial-history",
            headers=_headers(outsider.external_subject),
        )

    assert history.status_code == 503
    assert history.json()["error"]["code"] == "SOURCE_UNAVAILABLE"
    assert statement.status_code == 503
    assert statement.json()["error"]["code"] == "SOURCE_UNAVAILABLE"
    assert denied.status_code == 403
