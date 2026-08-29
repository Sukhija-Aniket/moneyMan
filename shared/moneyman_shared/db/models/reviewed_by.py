from typing import Literal, get_args

ReviewedBy = Literal["system", "human"]

REVIEWED_BY_VALUES: tuple[str, ...] = get_args(ReviewedBy)
