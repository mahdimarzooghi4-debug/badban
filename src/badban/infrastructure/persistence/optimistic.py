from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


class OptimisticConcurrencyError(RuntimeError):
    pass


async def update_with_expected_version(
    session: AsyncSession,
    table: Any,
    record_id: Any,
    expected_version: int,
    values: dict[str, Any],
) -> None:
    statement = (
        update(table)
        .where(table.c.id == record_id, table.c.version == expected_version)
        .values(**values, version=expected_version + 1)
    )
    result = await session.execute(statement)
    if getattr(result, "rowcount", 0) != 1:
        raise OptimisticConcurrencyError(
            f"Expected version {expected_version} did not match current record version"
        )
