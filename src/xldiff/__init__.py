"""xldiff: fingerprint .xlsx workbooks and estimate how similar two of them are."""

from .fingerprint import K, Fingerprint, SheetStats, bottom_k, fingerprint, r1c1
from .similarity import Similarity, jaccard, similarity, sketch_jaccard

__version__ = "0.1.0"

__all__ = [
    "K",
    "Fingerprint",
    "SheetStats",
    "Similarity",
    "bottom_k",
    "fingerprint",
    "jaccard",
    "r1c1",
    "similarity",
    "sketch_jaccard",
    "__version__",
]
