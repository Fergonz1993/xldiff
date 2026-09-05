"""xldiff: fingerprint .xlsx workbooks and estimate how similar two of them are."""

from .fingerprint import K, Fingerprint, SheetStats, bottom_k, fingerprint, r1c1
from .lineage import KEEP, PIVOT, Version, lineage, parse_date, parse_version
from .similarity import Similarity, jaccard, similarity, sketch_jaccard

__version__ = "0.1.0"

__all__ = [
    "K",
    "KEEP",
    "PIVOT",
    "Fingerprint",
    "SheetStats",
    "Similarity",
    "Version",
    "bottom_k",
    "fingerprint",
    "jaccard",
    "lineage",
    "parse_date",
    "parse_version",
    "r1c1",
    "similarity",
    "sketch_jaccard",
    "__version__",
]
