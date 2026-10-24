"""Create a small, entirely invented model history for the README example."""

from __future__ import annotations

import argparse
from pathlib import Path

from workbooks import build_workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--backend", choices=("openpyxl", "mog"), default="openpyxl")
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    paths = [args.directory / f"model_v{version}.xlsx" for version in range(1, 5)]
    if any(path.exists() for path in paths):
        parser.error("The output directory already contains a demo workbook; choose a new directory.")
    for version, path in enumerate(paths, 1):
        formula = "=Inputs!B2*Inputs!B3" if version < 3 else "=Inputs!B2*Inputs!B3-Inputs!B4"
        build_workbook(path, {
            "Inputs": [["Item", "Amount"], ["Units", 10 + version], ["Unit price", 20], ["Cost", 5]],
            "Summary": [["Revenue"], [formula]],
        }, backend=args.backend)
    print(f"Created {len(paths)} invented workbooks in {args.directory}")


if __name__ == "__main__":
    main()
