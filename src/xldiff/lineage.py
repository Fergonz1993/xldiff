"""Order the versions of a workbook lineage and pick the ones worth keeping.

The premise: in a folder holding a dozen versions of the same model, what matters is not the newest few but the
points where the model changed shape. A run of versions that barely differ is one idea being polished, and the
last of them is its mature state; the next version, if it scores far below its predecessor, is a new idea. So the
selection keeps the newest version, the version just before every such pivot, and then fills the remaining budget
from the newest down.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal

from .fingerprint import Fingerprint, fingerprint_cached
from .similarity import similarity

KEEP = 5
PIVOT = 0.6

VERSION_TOKEN = re.compile(r"(?<![A-Za-z0-9])[vV](\d+(?:[._]\d+)*)(?![A-Za-z0-9])")
ISO_DATE = re.compile(r"(?<!\d)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)")
DMY_DATE = re.compile(r"(?<!\d)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)")
COMPACT_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(\d{2})(\d{2})(?!\d)")

Decision = Literal["keep", "drop"]


@dataclass
class Version:
    """One member of a lineage: a file, where it sits in the order, and what to do with it."""

    path: str
    version: tuple[int, ...]  # from a v1 / v2.3 / v2_3 token in the file name; () when absent
    date: int  # YYYYMMDD from the name; 0 when absent
    mtime: int
    fingerprint: Fingerprint
    sim_prev: float | None
    decision: Decision
    reason: str  # newest, before pivot, fill, dropped, unreadable

    @property
    def label(self) -> str:
        """How to name this version in a report: its version token, else its date, else the file name."""
        if self.version:
            return "v" + ".".join(str(p) for p in self.version)
        if self.date:
            return str(self.date)
        return os.path.splitext(os.path.basename(self.path))[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "label": self.label,
            "version": list(self.version),
            "date": self.date,
            "mtime": self.mtime,
            "fingerprint": self.fingerprint.summary(),
            "sim_prev": self.sim_prev,
            "decision": self.decision,
            "reason": self.reason,
        }


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def parse_version(path: str | os.PathLike[str]) -> tuple[int, ...]:
    """The version token in a file name: v1 -> (1,), v2.3 and v2_3 -> (2, 3), V10 -> (10,), none -> ().

    The last token in the name wins, since a name usually ends with its version.
    """
    tokens = VERSION_TOKEN.findall(_stem(os.fspath(path)))
    if not tokens:
        return ()
    return tuple(int(part) for part in re.split(r"[._]", tokens[-1]))


def parse_date(path: str | os.PathLike[str]) -> int:
    """The date in a file name as YYYYMMDD: ISO first, then DD-MM-YYYY, then compact. 0 when there is none."""
    stem = _stem(os.fspath(path))
    for pattern, order in ((ISO_DATE, (1, 2, 3)), (DMY_DATE, (3, 2, 1)), (COMPACT_DATE, (1, 2, 3))):
        for match in pattern.finditer(stem):
            year, month, day = (int(match.group(g)) for g in order)
            if 1 <= month <= 12 and 1 <= day <= 31:
                return year * 10000 + month * 100 + day
    return 0


def _mtime(path: str) -> int:
    try:
        return int(os.stat(path).st_mtime)
    except OSError:
        return 0


def group_versions(paths: Iterable[str | os.PathLike[str]]) -> dict[Any, list[str]]:
    """Group files that are the same version: the same v-token and date, or failing both, the same file name.

    Two copies of one version in different folders are one version, so a lineage of eight versions kept in two
    places is still eight points on the timeline.
    """
    groups: dict[Any, list[str]] = {}
    for raw in paths:
        path = os.fspath(raw)
        version, date = parse_version(path), parse_date(path)
        key = (version, date) if version or date else _stem(path).lower()
        groups.setdefault(key, []).append(path)
    return groups


def _select(count: int, sims: dict[int, float], keep: int, pivot: float) -> tuple[set[int], set[int]]:
    """Which positions to keep, and which positions are the version just before a pivot."""
    before_pivot = {i - 1 for i, score in sims.items() if score < pivot}
    if count <= keep:
        return set(range(count)), before_pivot
    chosen = {count - 1} | before_pivot
    for i in range(count - 2, -1, -1):  # fill the rest of the budget from the newest down
        if len(chosen) >= keep:
            break
        chosen.add(i)
    if len(chosen) > keep:  # more pivots than budget: the newest, plus the pivots with the biggest drops
        steepest = sorted(before_pivot, key=lambda i: sims[i + 1])
        chosen = {count - 1} | set(steepest[: keep - 1])
    return chosen, before_pivot


def lineage(
    paths: Iterable[str | os.PathLike[str]],
    keep: int = KEEP,
    pivot: float = PIVOT,
    cache: dict[str, Any] | None = None,
) -> list[Version]:
    """Fingerprint every file, order the lineage, and mark each version keep or drop.

    Ordering is by version token, then date in the name, then mtime. Files that cannot be read are ordered by
    name and placed first, because nothing can be said about where they belong; each is dropped as unreadable
    unless it is the only thing left, in which case the newest of them is kept.
    """
    entries: list[Version] = []
    for members in group_versions(paths).values():
        path = max(members, key=lambda p: (_mtime(p), p))
        entries.append(
            Version(
                path=path,
                version=parse_version(path),
                date=parse_date(path),
                mtime=_mtime(path),
                fingerprint=fingerprint_cached(path, cache),
                sim_prev=None,
                decision="drop",
                reason="dropped",
            )
        )
    readable = sorted((e for e in entries if e.fingerprint.error is None), key=lambda e: (e.version, e.date, e.mtime))
    unreadable = sorted((e for e in entries if e.fingerprint.error is not None), key=lambda e: _stem(e.path).lower())
    ordered = unreadable + readable

    sims = {}
    for i in range(1, len(readable)):
        score = similarity(readable[i - 1].fingerprint, readable[i].fingerprint).score
        readable[i].sim_prev = score
        sims[len(unreadable) + i] = score

    chosen, before_pivot = _select(len(ordered), sims, keep, pivot)
    for i, version in enumerate(ordered):
        newest = i == len(ordered) - 1
        if version.fingerprint.error is not None and not newest:
            version.decision, version.reason = "drop", "unreadable"
        elif newest:
            version.decision, version.reason = "keep", "newest"
        elif i in chosen:
            version.decision, version.reason = "keep", "before pivot" if i in before_pivot else "fill"
        else:
            version.decision, version.reason = "drop", "dropped"
    return ordered
