from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert
from app.domain.enums import AlertKind, AlertSeverity


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_idempotent(
        self,
        *,
        user_id: int,
        kind: AlertKind,
        severity: AlertSeverity,
        summary: str,
        dedup_key: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Returns True if inserted, False if duplicate."""
        stmt = (
            insert(Alert)
            .values(
                user_id=user_id,
                kind=kind,
                severity=severity,
                summary=summary,
                dedup_key=dedup_key,
                payload=payload,
            )
            .on_conflict_do_nothing(index_elements=["dedup_key"])
            .returning(Alert.id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def open_for_user(self, user_id: int) -> list[Alert]:
        res = await self.session.execute(
            select(Alert)
            .where(Alert.user_id == user_id, Alert.acknowledged_at.is_(None))
            .order_by(Alert.created_at.desc())
        )
        return list(res.scalars())

    async def list_for_user(self, user_id: int, limit: int = 50) -> list[Alert]:
        res = await self.session.execute(
            select(Alert)
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars())

    async def acknowledge(self, alert: Alert, by_user_id: int, when: datetime) -> None:
        alert.acknowledged_at = when
        alert.acknowledged_by_id = by_user_id

    async def by_id(self, alert_id: int) -> Optional[Alert]:
        return await self.session.get(Alert, alert_id)
