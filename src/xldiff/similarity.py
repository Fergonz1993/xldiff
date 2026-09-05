"""Estimate how similar two workbooks are from their fingerprints.

Everything here is an estimate. Sketches are lossy by design: they answer "did this workbook change a little or a
lot" cheaply, and they do not tell you which cell moved. For that, see the tools listed in the README.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .fingerprint import K, Fingerprint

SHEET_WEIGHT = 0.3
CONTENT_WEIGHT = 0.7


@dataclass
class Similarity:
    sheets: float  # Jaccard of the sheet-name sets
    formulas: float | None  # bottom-k Jaccard estimate; None when neither side has formulas
    values: float | None  # same, for cell values
    score: float  # 0.3 * sheets + 0.7 * (formulas, or values when there are no formulas)

    def to_dict(self) -> dict[str, Any]:
        return {"sheets": self.sheets, "formulas": self.formulas, "values": self.values, "score": self.score}


def jaccard(a: Iterable[Any], b: Iterable[Any]) -> float:
    """Plain set Jaccard. Two empty sets count as identical."""
    left, right = set(a), set(b)
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def sketch_jaccard(a: Sequence[int], b: Sequence[int], k: int = K) -> float | None:
    """Bottom-k Jaccard estimate: of the k smallest hashes in the union, the share both sides carry.

    Returns None when neither side has anything to compare, and 0.0 when only one side does.
    """
    if not a and not b:
        return None
    if not a or not b:
        return 0.0
    left, right = set(a), set(b)
    union_k = set(sorted(left | right)[:k])
    return len(union_k & left & right) / len(union_k)


def similarity(a: Fingerprint, b: Fingerprint, k: int = K) -> Similarity:
    """Compare two fingerprints.

    The score weighs sheet overlap at 0.3 and content at 0.7. Content means formulas when either side has any,
    because a rewrite shows there first; workbooks that are pure data fall back to values. Callers who want
    another weighting have every component on the returned object.
    """
    sheets = jaccard(a.sheets, b.sheets)
    formulas = sketch_jaccard(a.formula_sketch, b.formula_sketch, k)
    values = sketch_jaccard(a.value_sketch, b.value_sketch, k)
    content = formulas if formulas is not None else values
    score = sheets if content is None else SHEET_WEIGHT * sheets + CONTENT_WEIGHT * content
    return Similarity(sheets=sheets, formulas=formulas, values=values, score=score)
