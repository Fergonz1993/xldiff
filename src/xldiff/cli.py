"""Command line interface: xldiff fingerprint | compare | lineage."""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import zipfile
from typing import Any, Iterable, Sequence

from . import __version__
from .fingerprint import K, Fingerprint, fingerprint_cached, load_cache, save_cache
from .lineage import KEEP, PIVOT, Version, lineage
from .similarity import similarity

OK = 0
UNREADABLE = 1
USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xldiff",
        description="Fingerprint .xlsx workbooks, estimate how similar two of them are, "
        "and pick the versions of a lineage worth keeping.",
    )
    parser.add_argument("--version", action="version", version=f"xldiff {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    fingerprint_command = commands.add_parser("fingerprint", help="read one or more workbooks and report what is in them")
    fingerprint_command.add_argument("files", nargs="+", metavar="FILE")

    compare_command = commands.add_parser("compare", help="estimate how similar two workbooks are")
    compare_command.add_argument("a", metavar="A")
    compare_command.add_argument("b", metavar="B")

    lineage_command = commands.add_parser("lineage", help="order the versions of a model and pick which to keep")
    lineage_command.add_argument("paths", nargs="+", metavar="PATH", help="files, or directories to scan for *.xlsx")
    lineage_command.add_argument("--keep", type=int, default=KEEP, metavar="N", help=f"how many versions to keep (default {KEEP})")
    lineage_command.add_argument("--pivot", type=float, default=PIVOT, metavar="F", help=f"score below which a pair is a pivot (default {PIVOT})")
    lineage_command.add_argument("--recursive", action="store_true", help="scan directories recursively")

    for command in (fingerprint_command, compare_command, lineage_command):
        command.add_argument("--json", action="store_true", dest="as_json", help="print machine-readable JSON instead of a table")
        command.add_argument("--cache", metavar="FILE", help="reuse fingerprints from this JSON file, keyed by path|size|mtime")
    return parser


def collect(paths: Iterable[str], recursive: bool) -> list[str]:
    """Expand directories into the workbooks they hold, keeping the caller's order and dropping duplicates."""
    found: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            pattern = os.path.join(path, "**", "*.xlsx") if recursive else os.path.join(path, "*.xlsx")
            found.extend(sorted(glob.glob(pattern, recursive=recursive)))
        else:
            found.append(path)
    return list(dict.fromkeys(p for p in found if not os.path.basename(p).startswith("~$")))


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def print_fingerprints(prints: Sequence[Fingerprint]) -> None:
    for fp in prints:
        if fp.error:
            print(f"{fp.path}\n  unreadable: {fp.error}")
            continue
        print(f"{fp.path}\n  {fp.size:,} bytes, {len(fp.sheets)} sheets, {fp.total_cells:,} cells")
        print(f"  {'sheet':<28}{'cells':>10}{'formulas':>10}{'values':>10}")
        for name, stats in fp.sheets.items():
            print(f"  {name[:28]:<28}{stats.cells:>10,}{stats.formulas:>10,}{stats.values:>10,}")
        print(f"  {'total':<28}{fp.total_cells:>10,}{fp.total_formulas:>10,}{fp.total_values:>10,}")
        print(f"  sketches: {len(fp.formula_sketch)} formula hashes, {len(fp.value_sketch)} value hashes (bottom-{K})")


def print_lineage(versions: Sequence[Version], pivot: float) -> None:
    kept = sum(1 for v in versions if v.decision == "keep")
    print(f"{len(versions)} versions, keeping {kept}")
    for version in versions:
        fp = version.fingerprint
        broken = fp.error is not None
        mark = "KEEP" if version.decision == "keep" else "REVIEW" if broken else "    "
        flag = "PIVOT" if version.sim_prev is not None and version.sim_prev < pivot else ""
        sheets = "-" if broken else f"{len(fp.sheets)}"
        formulas = "-" if broken else f"{fp.total_formulas:,}"
        values = "-" if broken else f"{fp.total_values:,}"
        print(
            f"  {mark} {version.label[:16]:<16}"
            f" sheets={sheets:>3} formulas={formulas:>7} values={values:>9}"
            f" sim_prev={_fmt(version.sim_prev):<6} {flag:<5} {version.reason:<12} {version.path}"
        )
    for version in versions:
        if version.fingerprint.error:
            print(f"  ! {version.path}: {version.fingerprint.error}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "lineage":
        if args.keep < 1:
            parser.error("--keep must be a positive integer")
        if not 0 <= args.pivot <= 1:
            parser.error("--pivot must be between 0 and 1")
        inputs = collect(args.paths, args.recursive)
    elif args.command == "compare":
        inputs = [args.a, args.b]
    else:
        inputs = args.files
    if args.cache:
        if os.path.splitext(args.cache)[1].lower() in {".xlsx", ".xlsm", ".xls", ".xlsb", ".xltx", ".xltm", ".xlam"} or zipfile.is_zipfile(args.cache):
            parser.error("--cache must name a JSON file, not a workbook")
        for path in inputs:
            aliases_input = os.path.realpath(args.cache) == os.path.realpath(path)
            try:
                aliases_input = aliases_input or os.path.samefile(args.cache, path)
            except OSError:
                pass
            if aliases_input:
                parser.error("--cache must not overwrite an input file")
    cache: dict[str, Any] | None = load_cache(args.cache) if args.cache else None
    status = OK

    if args.command == "fingerprint":
        prints = [fingerprint_cached(path, cache) for path in args.files]
        status = UNREADABLE if any(fp.error for fp in prints) else OK
        if args.as_json:
            print(json.dumps([fp.to_dict() for fp in prints], indent=2))
        else:
            print_fingerprints(prints)

    elif args.command == "compare":
        a, b = (fingerprint_cached(path, cache) for path in (args.a, args.b))
        status = UNREADABLE if (a.error or b.error) else OK
        result = similarity(a, b)
        if args.as_json:
            print(json.dumps({"a": a.path, "b": b.path} | result.to_dict(), indent=2))
        else:
            print(f"A {a.path}\nB {b.path}")
            for name in ("sheets", "formulas", "values", "score"):
                print(f"  {name:<9}{_fmt(getattr(result, name))}")
            for fp in (a, b):
                if fp.error:
                    print(f"  ! {fp.path}: {fp.error}")

    else:
        paths = inputs
        if not paths:
            print("xldiff: no .xlsx files found in the given paths", file=sys.stderr)
            return USAGE
        versions = lineage(paths, keep=args.keep, pivot=args.pivot, cache=cache)
        status = UNREADABLE if any(v.fingerprint.error for v in versions) else OK
        if args.as_json:
            payload = {
                "versions": [v.to_dict() for v in versions],
                "keep": [v.path for v in versions if v.decision == "keep"],
            }
            print(json.dumps(payload, indent=2))
        else:
            print_lineage(versions, args.pivot)

    if args.cache and cache is not None:
        save_cache(args.cache, cache)
    return status


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
