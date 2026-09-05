"""xldiff: fingerprint .xlsx workbooks and estimate how similar two of them are."""

from .fingerprint import K, Fingerprint, SheetStats, bottom_k, fingerprint, r1c1

__version__ = "0.1.0"

__all__ = ["K", "Fingerprint", "SheetStats", "bottom_k", "fingerprint", "r1c1", "__version__"]
