from typing import Literal, get_args

ReviewStatus = Literal["pending", "confirmed", "not_transaction", "duplicate"]

REVIEW_STATUSES: tuple[str, ...] = get_args(ReviewStatus)
