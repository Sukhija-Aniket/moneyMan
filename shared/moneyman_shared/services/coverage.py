import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Generic date-range coverage tracking, shared by synced_ranges (backend-owned: fetch AND
# extraction both fully done) and fetched_ranges (shared: fetch alone done, regardless of
# extraction outcome — see moneyman_shared.db.models.fetched_range). Gap computation always
# diffs against the FULL row set for the user (never assumes rows are merged), so correctness
# never depends on merge_insert_range having run first — merging is a maintenance
# optimization (fewer rows to scan next time), not a correctness requirement.

_ONE_DAY = timedelta(days=1)


def compute_gaps(
    covered: list[tuple[date, date]], date_from: date, date_to: date
) -> list[tuple[date, date]]:
    """Given the user's existing covered ranges (any order, possibly overlapping/touching)
    and a requested [date_from, date_to], returns the sub-ranges of the request NOT covered
    by any of them, in ascending order.

    Pure function (no DB access) so it's trivially unit-testable against cases like:
    covered=[(20,50), (54,70)], request=(40,60) -> gaps=[(51,53)].
    """
    relevant = sorted(
        (c_from, c_to) for c_from, c_to in covered if c_from <= date_to and c_to >= date_from
    )

    # Coalesce overlapping/touching covered ranges into one interval list.
    coalesced: list[tuple[date, date]] = []
    for c_from, c_to in relevant:
        if coalesced and c_from <= coalesced[-1][1] + _ONE_DAY:
            coalesced[-1] = (coalesced[-1][0], max(coalesced[-1][1], c_to))
        else:
            coalesced.append((c_from, c_to))

    # Subtract the coalesced "already covered" intervals from [date_from, date_to].
    gaps: list[tuple[date, date]] = []
    cursor = date_from
    for c_from, c_to in coalesced:
        if c_from > cursor:
            gaps.append((cursor, min(c_from - _ONE_DAY, date_to)))
        cursor = max(cursor, c_to + _ONE_DAY)
        if cursor > date_to:
            break
    if cursor <= date_to:
        gaps.append((cursor, date_to))

    return gaps


async def get_covered_ranges(db: AsyncSession, model, user_id: uuid.UUID) -> list[tuple[date, date]]:
    result = await db.execute(select(model).where(model.user_id == user_id))
    return [(row.date_from, row.date_to) for row in result.scalars().all()]


async def merge_insert_range(db: AsyncSession, model, user_id: uuid.UUID, date_from: date, date_to: date) -> None:
    """Inserts [date_from, date_to] as newly covered, merging with any existing rows of
    `model` that touch or overlap it (deleting them and inserting a single row spanning the
    union) instead of accumulating a disjoint row. Not committed here — caller controls the
    transaction boundary."""
    result = await db.execute(
        select(model).where(
            model.user_id == user_id,
            model.date_from <= date_to + _ONE_DAY,
            model.date_to >= date_from - _ONE_DAY,
        )
    )
    overlapping = result.scalars().all()

    merged_from, merged_to = date_from, date_to
    for row in overlapping:
        merged_from = min(merged_from, row.date_from)
        merged_to = max(merged_to, row.date_to)
        await db.delete(row)

    await db.flush()
    db.add(model(user_id=user_id, date_from=merged_from, date_to=merged_to))
