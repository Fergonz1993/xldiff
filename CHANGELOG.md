# Changelog

## 0.1.1 - 2026-10-24

Experimental public release under the MIT license. Requires Python 3.11 or
newer and has no runtime dependencies.

### Changed

- Same-version grouping collapses only byte-identical files within a candidate
  group. Files with different contents remain separate, even with matching
  version tokens.
- Unreadable lineage inputs use `decision: "review"` and `reason: "unreadable"`.
  They remain visible even when every input is unreadable. They are not `drop`
  suggestions, and unreadable inputs still produce exit code 1.
- Invalid `keep` and `pivot` values are rejected. The CLI reports usage errors.
- The CLI rejects cache destinations that could overwrite an input workbook,
  including aliases to the same existing file.

### Added

- Versioned wheel, source distribution, and `SHA256SUMS.txt` distribution through
  the [GitHub release](https://github.com/Fergonz1993/xldiff/releases/tag/v0.1.1).
  This project does not publish to PyPI. The PyPI name belongs to an unrelated
  package.
- An invented four-version example generator with an output directory argument.
  It uses openpyxl from the development extras by default, with an optional
  `--backend mog` for configured hosts.
- Installation, interpretation, update, contribution-policy, and owner
  maintenance documentation.

The existing fingerprint, comparison, and lineage interfaces otherwise remain
the same. Processing remains local. xldiff does not recalculate formulas or
modify or delete workbook files. Similarity scores cannot justify deletion.

## 0.1.0

Initial development version with fingerprint, compare, and lineage commands,
JSON output, and an optional fingerprint cache.
