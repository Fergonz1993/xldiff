# xldiff

`xldiff` fingerprints `.xlsx` workbooks by reading the zip directly, with no Excel and no spreadsheet engine
involved, and estimates how similar two of them are. It looks at formula structure and at cell values, and
ignores everything else. Given a folder holding many versions of one model, it orders them and picks the few
worth keeping.

Zero runtime dependencies, Python 3.11 or newer.

## Install

```sh
pip install .            # from a clone
uv tool install .        # or, with uv
uvx --from . xldiff lineage models/
```

For development:

```sh
pip install -e '.[dev]' && pytest -q
```

## Commands

### fingerprint

```
$ xldiff fingerprint model_v4.xlsx
model_v4.xlsx
  6,602 bytes, 3 sheets, 114 cells
  sheet                            cells  formulas    values
  Inputs                              16         0        16
  Cashflow                            88        44        44
  Summary                             10         5         5
  total                              114        49        65
  sketches: 49 formula hashes, 65 value hashes (bottom-256)
```

`formulas` counts distinct formulas after normalization, not formula cells: a formula filled down 500 rows is
one formula. `--json` prints the same thing with both sketches included.

### compare

```
$ xldiff compare model_v4.xlsx model_v5.xlsx
A model_v4.xlsx
B model_v5.xlsx
  sheets   1.000
  formulas 0.053
  values   0.956
  score    0.337
```

The two files share their sheet names and almost all of their data, but the formulas behind that data were
rewritten. `--json` prints the four numbers plus both paths.

### lineage

```
$ xldiff lineage . --keep 5
8 versions, keeping 5
       v1               sheets=  3 formulas=     46 values=       56 sim_prev=-            dropped      model_v1.xlsx
       v2               sheets=  3 formulas=     47 values=       59 sim_prev=0.985        dropped      model_v2.xlsx
       v3               sheets=  3 formulas=     48 values=       62 sim_prev=0.985        dropped      model_v3.xlsx
  KEEP v4               sheets=  3 formulas=     49 values=       65 sim_prev=0.986        before pivot model_v4.xlsx
  KEEP v5               sheets=  3 formulas=     50 values=       68 sim_prev=0.337  PIVOT fill         model_v5.xlsx
  KEEP v6               sheets=  3 formulas=     51 values=       71 sim_prev=0.986        fill         model_v6.xlsx
  KEEP v7               sheets=  3 formulas=     52 values=       74 sim_prev=0.987        fill         model_v7.xlsx
  KEEP v8               sheets=  3 formulas=     53 values=       77 sim_prev=0.987        newest       model_v8.xlsx
```

`PATH` may be a file or a directory; directories are scanned for `*.xlsx`, non-recursively unless you pass
`--recursive`. `--json` prints one record per version (sheet counts only, no sketches) and the list of paths to
keep, which is the part a cleanup script wants.

Exit codes: 0 on success, 2 on a usage error, 1 when some input could not be read. An unreadable file never
stops the run; the rest is still reported.

## How similarity is computed

Every workbook produces two sets of items:

- **formulas**, as `sheet|R1C1`. Each formula is rewritten with offsets relative to the cell holding it, so
  `=A2*B$1` in `C2` and the same formula filled into `C500` are one item, and a row inserted above a block does
  not look like a rewrite. References written with `$` stay absolute: in `C3`, `A1` becomes `R[-2]C[-2]` while
  `$A$1` becomes `R1C1`, which keeps a hard-coded anchor distinguishable from a relative one.
- **values**, as `sheet|column|text`. Shared strings, inline strings, booleans and numbers all resolve to their
  text, and a formula cell contributes its cached result when the workbook has one.

Anchoring a value on its column rather than its cell is a deliberate trade: **an inserted row leaves the value
set untouched, an inserted column moves every item in it.** Row insertion is the common edit in a model that
grows, so this is usually what you want, but a workbook reorganized column-wise will read as a bigger change
than it is.

Each set is reduced to a bottom-k sketch: the k smallest 64-bit BLAKE2b hashes, k = 256. Two sketches are
compared by taking the k smallest hashes of their union and asking what share of those both sides carry, which
estimates the Jaccard overlap of the full sets. Below 256 items the estimate is exact; above it, it is a sample,
and small changes in a very large workbook can move the number by more than they should.

The headline score is

```
0.3 * sheets + 0.7 * formulas          when either side has formulas
0.3 * sheets + 0.7 * values            when neither does
sheets                                 when there is no content at all
```

where `sheets` is the plain Jaccard of the sheet-name sets. The score is formula-first on purpose: a model is
its formulas, and swapping in a new month of data should not read as a new model. If the data is what you care
about, read the `values` component, which every output exposes separately, and weigh it yourself.

## How lineage selection works

Versions come from file names: a `v1`, `v2.3`, `v2_3` or `V10` token, a date (`2026-01-30`, `30-01-2026`,
`20260130`), then mtime as the tie-breaker. Files carrying the same token are one version, so a copy of `v3` in
a backup folder does not become a second point on the timeline.

Consecutive versions are then compared. A pair scoring below `--pivot` (0.6 by default) is a pivot: the model
changed shape there. Selection keeps

1. the newest version,
2. the version just before every pivot, which is the mature state of the approach that was abandoned,
3. then, until `--keep` is reached (5 by default), the remaining versions from the newest down.

If the pivots alone overflow the budget, the newest plus the pivots with the steepest drops win. Files that
cannot be read sort first by name and are dropped as unreadable, unless nothing readable is left, in which case
the last of them is kept.

`--cache FILE` stores fingerprints in JSON keyed by `path|size|mtime`, which is worth it when you run over the
same few hundred workbooks repeatedly.

## Limits

- `.xlsx` and `.xlsm` only. `.xlsb` and `.xls` are reported as unsupported rather than parsed.
- Formatting, charts, VBA, defined names, comments and pivot caches are ignored entirely. Two workbooks that
  differ only in styling are identical to `xldiff`.
- Similarity is an estimate, not a diff. It answers "how much of this changed", never "which cell changed".
- Conflict-copy and duplicate markers (`(1)`, `copy`, ` 2`) are not special-cased. Such a file is grouped by
  whatever version token its name carries, or stands alone as its own version.
- Cells with no `r` attribute are skipped, and continuation cells of a shared formula carry no formula text of
  their own (they normalize to the same R1C1 as their master, so the sketch is unaffected).
- Formula cells written by tools that store no cached result contribute nothing to the value sketch.
- The parser reads the XML with regexes rather than a full parser: an `A1`-shaped token inside a string literal
  in a formula is rewritten like a reference.

## When to use something else

- **Microsoft Spreadsheet Compare** (ships with Office Professional on Windows) for a cell-by-cell visual diff
  of two workbooks, with formulas, values and formatting highlighted.
- **Git-based Excel diff tooling** — an xlsx `textconv` filter, or a hosted service such as xltrail — when you
  want a reviewable history of changes rather than a number.
- Either of those when you need to know *what* changed. `xldiff` is for the question that comes first: of these
  forty files, which ones are actually different, and which can go.

## License

MIT. See [LICENSE](LICENSE).
