"""Content fingerprints for .xlsx workbooks, read straight out of the zip.

No Excel, no spreadsheet engine, no third-party library: a workbook is a zip of XML parts, so the reader walks
the parts it needs (``xl/workbook.xml`` for sheet names, ``xl/sharedStrings.xml`` for text, one part per sheet)
with lenient regexes and hashes what it finds.

Two sketches come out of every workbook:

* formulas, as ``sheet|R1C1``. Rewriting each formula in R1C1 (offsets relative to the cell holding it) means the
  same formula filled down a column collapses to one item, and a row inserted above a block does not look like a
  rewrite.
* values, as ``sheet|column|text``. Anchoring on the column instead of the cell means an inserted row leaves the
  set alone while an inserted column moves every item in it.

Each set is reduced to a bottom-k sketch (the ``k`` smallest 64-bit hashes), which is what makes comparing two
large workbooks cheap and a cache of thousands of them small.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from typing import Any, Iterable

K = 256

# A cell is <c r="B7" t="s"><v>3</v></c> or <c r="B7"/>. Attributes are read separately so their order does not
# matter, and the body is grabbed whole because values and formulas both live inside it.
CELL = re.compile(rb"<c\s+([^>]*?)(?:/>|>(.*?)</c>)", re.S)
CELL_REF = re.compile(rb'\br="([A-Z]{1,3})(\d+)"')
CELL_TYPE = re.compile(rb'\bt="([^"]+)"')
FORMULA = re.compile(rb"<f[^>]*>(.*?)</f>", re.S)
VALUE = re.compile(rb"<v[^>]*>(.*?)</v>", re.S)
TEXT = re.compile(rb"<t[^>]*>(.*?)</t>", re.S)
SHARED_ITEM = re.compile(rb"<si[^>]*/>|<si[^>]*>(.*?)</si>", re.S)

SHEET_TAG = re.compile(r"<sheet\b[^>]*/?>")
RELATIONSHIP_TAG = re.compile(r"<Relationship\b[^>]*/?>")
NAME_ATTR = re.compile(r'\bname="([^"]*)"')
RID_ATTR = re.compile(r'\br:id="([^"]+)"')
ID_ATTR = re.compile(r'\bId="([^"]+)"')
TARGET_ATTR = re.compile(r'\bTarget="([^"]*)"')

# A1-style reference. The lookarounds keep function names (LOG10() and friends) and exponents (1.5E10) out.
REF = re.compile(r"(?<![A-Za-z0-9_.])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])")
ENTITY = re.compile(r"&(?:#(\d+)|#x([0-9A-Fa-f]+)|(amp|lt|gt|quot|apos));")
NAMED_ENTITIES = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}

UNSUPPORTED = {".xlsb": "binary workbook", ".xls": "legacy workbook"}


@dataclass
class SheetStats:
    cells: int
    formulas: int  # distinct R1C1-normalized formulas
    values: int  # non-empty cell values (cached formula results included)


@dataclass
class Fingerprint:
    path: str
    size: int
    sheets: dict[str, SheetStats]
    formula_sketch: list[int]  # bottom-k of 64-bit blake2b hashes of "sheet|R1C1"
    value_sketch: list[int]  # bottom-k of 64-bit blake2b hashes of "sheet|column|value_text"
    error: str | None = None  # set when the file is not a readable xlsx; sketches empty

    @property
    def total_cells(self) -> int:
        return sum(s.cells for s in self.sheets.values())

    @property
    def total_formulas(self) -> int:
        return sum(s.formulas for s in self.sheets.values())

    @property
    def total_values(self) -> int:
        return sum(s.values for s in self.sheets.values())

    def summary(self) -> dict[str, Any]:
        """The fingerprint without its sketches, for reports where the hashes are noise."""
        return {
            "path": self.path,
            "size": self.size,
            "sheets": {name: asdict(stats) for name, stats in self.sheets.items()},
            "error": self.error,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"formula_sketch": list(self.formula_sketch), "value_sketch": list(self.value_sketch)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Fingerprint":
        return cls(
            path=data["path"],
            size=data["size"],
            sheets={name: SheetStats(**stats) for name, stats in data["sheets"].items()},
            formula_sketch=list(data.get("formula_sketch", [])),
            value_sketch=list(data.get("value_sketch", [])),
            error=data.get("error"),
        )


def bottom_k(items: Iterable[str], k: int = K) -> list[int]:
    """The k smallest 64-bit hashes of a set of strings. One hash per item, so this is linear in workbook size."""
    hashes = {int.from_bytes(hashlib.blake2b(i.encode("utf8", "ignore"), digest_size=8).digest(), "big") for i in items}
    return sorted(hashes)[:k]


def column_number(letters: str) -> int:
    """A -> 1, Z -> 26, AA -> 27."""
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def r1c1(formula: str, col: int, row: int) -> str:
    """Rewrite A1 references as offsets from the cell holding the formula; $ references stay absolute.

    In cell C3, ``A1`` becomes ``R[-2]C[-2]``, ``$A$1`` becomes ``R1C1`` and ``A$1`` becomes ``R1C[-2]``.
    """

    def sub(m: re.Match[str]) -> str:
        abs_col, letters, abs_row, digits = m.groups()
        r = f"R{digits}" if abs_row else f"R[{int(digits) - row}]"
        c = f"C{column_number(letters)}" if abs_col else f"C[{column_number(letters) - col}]"
        return r + c

    return REF.sub(sub, formula)


def _unescape(text: str) -> str:
    if "&" not in text:
        return text

    def sub(m: re.Match[str]) -> str:
        dec, hexa, name = m.groups()
        if name:
            return NAMED_ENTITIES[name]
        return chr(int(dec) if dec else int(hexa, 16))

    return ENTITY.sub(sub, text)


def _decode(raw: bytes) -> str:
    return _unescape(raw.decode("utf8", "ignore"))


def _cell_text(body: bytes, cell_type: str, shared: list[str]) -> str:
    """The displayed value of a cell as text, or "" when the cell holds nothing."""
    if cell_type == "inlineStr":
        return "".join(_decode(t) for t in TEXT.findall(body))
    value = VALUE.search(body)
    if not value:
        return ""
    raw = _decode(value.group(1))
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell_type == "b":
        return "TRUE" if raw.strip() not in ("0", "false", "FALSE", "") else "FALSE"
    return raw


def scan_sheet(data: bytes, sheet: str, shared: list[str]) -> tuple[SheetStats, set[str], set[str]]:
    """Read one sheet part. Returns its stats plus the formula and value items it contributes."""
    cells = 0
    values = 0
    formulas: set[str] = set()
    value_items: set[str] = set()
    for match in CELL.finditer(data):
        ref = CELL_REF.search(match.group(1))
        if not ref:  # a cell with no r attribute; its position is implied by document order, which we do not track
            continue
        cells += 1
        column = ref.group(1).decode()
        row = int(ref.group(2))
        body = match.group(2) or b""
        type_attr = CELL_TYPE.search(match.group(1))
        cell_type = type_attr.group(1).decode() if type_attr else "n"
        formula = FORMULA.search(body)
        if formula:
            formulas.add(r1c1(_decode(formula.group(1)), column_number(column), row))
        text = _cell_text(body, cell_type, shared)
        if text:
            values += 1
            value_items.add(f"{sheet}|{column}|{text}")
    return (
        SheetStats(cells=cells, formulas=len(formulas), values=values),
        {f"{sheet}|{f}" for f in formulas},
        value_items,
    )


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        data = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings = []
    for match in SHARED_ITEM.finditer(data):
        body = match.group(1)
        strings.append("" if body is None else "".join(_decode(t) for t in TEXT.findall(body)))
    return strings


def _member(target: str) -> str:
    part = target.replace("\\", "/").lstrip("/")
    while part.startswith("../"):
        part = part[3:]
    return part if part.startswith("xl/") else "xl/" + part


def _sheet_members(archive: zipfile.ZipFile, names: set[str]) -> dict[str, str]:
    """Map zip member -> sheet name, through xl/workbook.xml and its relationships."""
    workbook = archive.read("xl/workbook.xml").decode("utf8", "ignore")
    try:
        rels = archive.read("xl/_rels/workbook.xml.rels").decode("utf8", "ignore")
    except KeyError:
        rels = ""
    targets = {}
    for tag in RELATIONSHIP_TAG.findall(rels):
        rid, target = ID_ATTR.search(tag), TARGET_ATTR.search(tag)
        if rid and target:
            targets[rid.group(1)] = target.group(1)
    members = {}
    for tag in SHEET_TAG.findall(workbook):
        name, rid = NAME_ATTR.search(tag), RID_ATTR.search(tag)
        if not name or not rid:
            continue
        member = _member(targets.get(rid.group(1), ""))
        if member in names:
            members[member] = _unescape(name.group(1))
    if not members:  # relationships missing or unreadable: fall back to the worksheet parts themselves
        for member in sorted(n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml")):
            members[member] = os.path.splitext(os.path.basename(member))[0]
    return members


def fingerprint(path: str | os.PathLike[str], k: int = K) -> Fingerprint:
    """Fingerprint one workbook. Never raises: an unreadable file comes back with ``error`` set and no sketches."""
    path = os.fspath(path)
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return Fingerprint(path, 0, {}, [], [], error=_describe(exc))
    extension = os.path.splitext(path)[1].lower()
    if extension in UNSUPPORTED:
        return Fingerprint(path, size, {}, [], [], error=f"{UNSUPPORTED[extension]} ({extension}) is not supported; xldiff reads .xlsx")
    sheets: dict[str, SheetStats] = {}
    formula_items: set[str] = set()
    value_items: set[str] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "xl/workbook.xml" not in names:
                return Fingerprint(path, size, {}, [], [], error="not a workbook: xl/workbook.xml is missing")
            shared = _shared_strings(archive)
            for member, sheet in _sheet_members(archive, names).items():
                stats, formulas, values = scan_sheet(archive.read(member), sheet, shared)
                sheets[sheet] = stats
                formula_items |= formulas
                value_items |= values
    except Exception as exc:  # a renamed csv, a truncated download, a corrupt part: record it and move on
        return Fingerprint(path, size, {}, [], [], error=_describe(exc))
    return Fingerprint(path, size, sheets, bottom_k(formula_items, k), bottom_k(value_items, k))


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:200]


def cache_key(path: str | os.PathLike[str]) -> str:
    stat = os.stat(path)
    return f"{os.path.abspath(os.fspath(path))}|{stat.st_size}|{int(stat.st_mtime)}"


def load_cache(path: str | os.PathLike[str]) -> dict[str, Any]:
    try:
        with open(path, encoding="utf8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        return {}
    return cache if isinstance(cache, dict) else {}


def save_cache(path: str | os.PathLike[str], cache: dict[str, Any]) -> None:
    """Replace the cache atomically without writing through file links."""
    path = os.path.abspath(os.fspath(path))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=os.path.dirname(path),
                                         prefix=".xldiff-cache-", suffix=".tmp", delete=False) as fh:
            temporary = fh.name
            json.dump(cache, fh)
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def fingerprint_cached(path: str | os.PathLike[str], cache: dict[str, Any] | None, k: int = K) -> Fingerprint:
    """Fingerprint, reusing a cache keyed by path|size|mtime. Pass ``None`` to skip the cache."""
    if cache is None:
        return fingerprint(path, k)
    try:
        key = cache_key(path)
    except OSError:
        return fingerprint(path, k)
    hit = cache.get(key)
    if hit is not None:
        try:
            return Fingerprint.from_dict(hit)
        except (KeyError, TypeError, ValueError):
            pass
    result = fingerprint(path, k)
    cache[key] = result.to_dict()
    return result
