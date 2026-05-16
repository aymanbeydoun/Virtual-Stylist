"""Closet-Gap analysis service.

Sends the current wardrobe to the model gateway, persists the findings,
and dedupes against any open findings the user already has (so re-running
the analysis doesn't create duplicates).

Affiliate suggestions are deferred to Phase 4 — the gap finding itself is
useful as a standalone product feature.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gaps import GapFinding, GapSeverity, GapStatus
from app.models.users import OwnerKind
from app.models.wardrobe import WardrobeItem
from app.services.model_gateway import get_model_gateway
from app.services.stylist_engine import _serialize_candidate


def _key(slot: str, title: str) -> str:
    """Dedupe key — same slot + similar title means same gap."""
    return f"{slot.lower()}::{title.strip().lower()[:80]}"


async def analyse_wardrobe(
    db: AsyncSession,
    *,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID,
    owner_label: str,
) -> list[GapFinding]:
    """Run the gap analysis end-to-end. Returns the freshly-inserted findings.

    Doesn't dismiss old open findings — that's the user's job. We only avoid
    creating new findings that match an existing open one.
    """
    items_q = select(WardrobeItem).where(
        WardrobeItem.owner_kind == owner_kind,
        WardrobeItem.owner_id == owner_id,
        WardrobeItem.status == "ready",
        WardrobeItem.deleted_at.is_(None),
    )
    items = list((await db.execute(items_q)).scalars().all())
    if not items:
        return []

    candidates = [_serialize_candidate(it) for it in items]

    gateway = get_model_gateway()
    result = await gateway.analyze_gaps(items=candidates, owner_label=owner_label)

    existing_q = select(GapFinding).where(
        GapFinding.owner_kind == owner_kind,
        GapFinding.owner_id == owner_id,
        GapFinding.status == GapStatus.open,
    )
    existing = list((await db.execute(existing_q)).scalars().all())
    seen = {_key(f.slot, f.title) for f in existing}

    inserted: list[GapFinding] = []
    for f in result.findings:
        slot = str(f.get("slot", "")).strip()
        title = str(f.get("title", "")).strip()
        if not slot or not title:
            continue
        if _key(slot, title) in seen:
            continue
        try:
            severity = GapSeverity(str(f.get("severity", "medium")).lower())
        except ValueError:
            severity = GapSeverity.medium
        gap = GapFinding(
            owner_kind=owner_kind,
            owner_id=owner_id,
            slot=slot,
            category_hint=str(f.get("category_hint") or "")[:80] or None,
            title=title[:200],
            rationale=str(f.get("rationale") or "")[:1000] or None,
            severity=severity,
            status=GapStatus.open,
            search_query=str(f.get("search_query") or "")[:200] or None,
        )
        db.add(gap)
        inserted.append(gap)
        seen.add(_key(slot, title))

    await db.commit()
    for g in inserted:
        await db.refresh(g)
    return inserted


async def dismiss(
    db: AsyncSession,
    *,
    gap_id: uuid.UUID,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID,
) -> bool:
    gap = (
        await db.execute(
            select(GapFinding).where(
                GapFinding.id == gap_id,
                GapFinding.owner_kind == owner_kind,
                GapFinding.owner_id == owner_id,
            )
        )
    ).scalar_one_or_none()
    if not gap or gap.status != GapStatus.open:
        return False
    gap.status = GapStatus.dismissed
    gap.dismissed_at = datetime.now(UTC)
    await db.commit()
    return True
