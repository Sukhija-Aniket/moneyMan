import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from moneyman_shared.db.models.category import Category

CREDIT_CATEGORY_NAMES = {"Income", "Returns"}

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
    marked is_system=True since the user didn't create them themselves. Each category is
    tagged debit or credit (see CREDIT_CATEGORY_NAMES) so the transaction category dropdown
    can be restricted to categories matching a given transaction's txn_type."""
    for name in DEFAULT_CATEGORY_NAMES:
        txn_type = "credit" if name in CREDIT_CATEGORY_NAMES else "debit"
        db.add(Category(user_id=user_id, name=name, is_system=True, txn_type=txn_type))
