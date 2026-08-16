import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.synced_range import SyncedRange

# Backend-owned: sync coverage tracking for range syncs. Gap computation always diffs
# against the FULL synced_ranges row set for the user (never assumes rows are merged), so
# correctness never depends on merge_insert_synced_range having run first — merging is a
# maintenance optimization (fewer rows to scan next time), not a correctness requirement.

_ONE_DAY = timedelta(days=1)


def compute_gaps(
    synced: list[tuple[date, date]], date_from: date, date_to: date
) -> list[tuple[date, date]]:
    """Given the user's existing synced ranges (any order, possibly overlapping/touching)
    and a requested [date_from, date_to], returns the sub-ranges of the request NOT covered
    by any synced range, in ascending order.

    Pure function (no DB access) so it's trivially unit-testable against cases like:
    synced=[(20,50), (54,70)], request=(40,60) -> gaps=[(51,53)].
    """
    relevant = sorted(
        (s_from, s_to) for s_from, s_to in synced if s_from <= date_to and s_to >= date_from
    )

    # Coalesce overlapping/touching synced ranges into one interval list.
    coalesced: list[tuple[date, date]] = []
    for s_from, s_to in relevant:
        if coalesced and s_from <= coalesced[-1][1] + _ONE_DAY:
            coalesced[-1] = (coalesced[-1][0], max(coalesced[-1][1], s_to))
        else:
            coalesced.append((s_from, s_to))

    # Subtract the coalesced "already synced" intervals from [date_from, date_to].
    gaps: list[tuple[date, date]] = []
    cursor = date_from
    for s_from, s_to in coalesced:
        if s_from > cursor:
            gaps.append((cursor, min(s_from - _ONE_DAY, date_to)))
        cursor = max(cursor, s_to + _ONE_DAY)
        if cursor > date_to:
            break
    if cursor <= date_to:
        gaps.append((cursor, date_to))

    return gaps


async def get_synced_ranges(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[date, date]]:
    result = await db.execute(select(SyncedRange).where(SyncedRange.user_id == user_id))
    return [(row.date_from, row.date_to) for row in result.scalars().all()]


async def merge_insert_synced_range(
    db: AsyncSession, user_id: uuid.UUID, date_from: date, date_to: date
) -> None:
    """Inserts [date_from, date_to] as newly synced, merging with any existing rows that
    touch or overlap it (deleting them and inserting a single row spanning the union)
    instead of accumulating a disjoint row. Not committed here — caller controls the
    transaction boundary."""
    result = await db.execute(
        select(SyncedRange).where(
            SyncedRange.user_id == user_id,
            SyncedRange.date_from <= date_to + _ONE_DAY,
            SyncedRange.date_to >= date_from - _ONE_DAY,
        )
    )
    overlapping = result.scalars().all()

    merged_from, merged_to = date_from, date_to
    for row in overlapping:
        merged_from = min(merged_from, row.date_from)
        merged_to = max(merged_to, row.date_to)
        await db.delete(row)

    await db.flush()
    db.add(SyncedRange(user_id=user_id, date_from=merged_from, date_to=merged_to))
