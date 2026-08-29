import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.category import Category

DEFAULT_CATEGORY_NAMES = [
    "General",
    "Food",
    "Groceries",
    "Travel",
    "Transport",
    "Medicines",
    "Health",
    "Shopping",
    "Bills & Utilities",
    "Entertainment",
    "Rent",
    "Education",
    "Income",
    "Transfer",
]


async def create_default_categories(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Seeds a new user's category list with a standard set of everyday categories,
    marked is_system=True since the user didn't create them themselves."""
    for name in DEFAULT_CATEGORY_NAMES:
        db.add(Category(user_id=user_id, name=name, is_system=True))
