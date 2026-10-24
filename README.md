# xldiff

xldiff is an experimental command-line tool that compares Excel workbook
structure and stored cell values. Version 0.1.1 requires Python 3.11 or newer,
has no runtime dependencies, and uses the MIT license.

It reads workbook ZIP and XML data locally. It does not upload workbook data,
run Excel, execute macros, recalculate formulas, or modify or delete workbook
files. Installation downloads the package from GitHub. An optional cache writes
a separate JSON file.

Use xldiff to identify versions that need closer review. A similarity score
cannot justify deletion, even when the score is 1.0. The tool ignores parts of
a workbook that may matter to you.

## Install version 0.1.1

**Do not run `pip install xldiff`. That command installs an unrelated PyPI
package.** This project keeps the xldiff name and does not publish to PyPI.

Install Python 3.11 or newer first. Then open a terminal and create a virtual
environment, which keeps this installation separate from other Python packages.

On macOS or Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "https://github.com/Fergonz1993/xldiff/releases/download/v0.1.1/xldiff-0.1.1-py3-none-any.whl"
xldiff --version
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "https://github.com/Fergonz1993/xldiff/releases/download/v0.1.1/xldiff-0.1.1-py3-none-any.whl"
.\.venv\Scripts\xldiff.exe --version
```

The version command should print `xldiff 0.1.1`. On Windows, use
`.\.venv\Scripts\xldiff.exe` in place of `xldiff` in the examples below.
The selected Python interpreter must be version 3.11 or newer.

If you already use uv, this optional command installs the same wheel as a tool:

```sh
uv tool install "https://github.com/Fergonz1993/xldiff/releases/download/v0.1.1/xldiff-0.1.1-py3-none-any.whl"
```

The [0.1.1 release](https://github.com/Fergonz1993/xldiff/releases/tag/v0.1.1)
provides these assets:

- [xldiff-0.1.1-py3-none-any.whl](https://github.com/Fergonz1993/xldiff/releases/download/v0.1.1/xldiff-0.1.1-py3-none-any.whl), the installable package.
- [xldiff-0.1.1.tar.gz](https://github.com/Fergonz1993/xldiff/releases/download/v0.1.1/xldiff-0.1.1.tar.gz), the source distribution.
- [SHA256SUMS.txt](https://github.com/Fergonz1993/xldiff/releases/download/v0.1.1/SHA256SUMS.txt), the package checksums.

To check a download, compare its SHA-256 checksum with the corresponding line
in `SHA256SUMS.txt` before installation. Use `shasum -a 256 FILE` on macOS,
`sha256sum FILE` on Linux, or `Get-FileHash FILE -Algorithm SHA256` in PowerShell.

## Try invented workbooks

The source distribution includes `examples/demo.py`. It creates four invented
workbook versions in the output directory you choose. No client data is included.

Download and extract `xldiff-0.1.1.tar.gz`. Open a terminal in the extracted
directory and activate your virtual environment. Install the development extras
for the default example generator:

```sh
python -m pip install -e ".[dev]"
python examples/demo.py demo-workbooks
xldiff fingerprint demo-workbooks/model_v1.xlsx
xldiff compare demo-workbooks/model_v1.xlsx demo-workbooks/model_v2.xlsx
xldiff compare demo-workbooks/model_v2.xlsx demo-workbooks/model_v3.xlsx
xldiff lineage demo-workbooks --keep 2
```

The default generator uses openpyxl, which is a development dependency.
xldiff itself does not need openpyxl to read workbooks. The first comparison
has changed input numbers. The second also has changed formula text.
Compare the separate `values` and `formulas` results.

If your host already has MOG configured, use the optional generator backend:

```sh
python examples/demo.py demo-workbooks-mog --backend mog
```

MOG is optional and is not installed by xldiff. The generator refuses to
overwrite an existing demo workbook. Use a new output directory for another run.

## Commands

Explicit workbook inputs can be `.xlsx` or `.xlsm`. Directory discovery in
`lineage` searches only for `*.xlsx`. Pass `.xlsm` paths explicitly.
Legacy `.xls` and binary `.xlsb` files are unsupported.

### Inspect workbooks with fingerprint

```sh
xldiff fingerprint model_v1.xlsx model_v2.xlsm
xldiff fingerprint model_v1.xlsx --json
```

The report includes file size, sheet names, cell counts, distinct normalized
formula counts, and nonempty value counts. A formula copied down many rows can
count as one distinct formula per sheet. The formula count is not a count of
formula cells. JSON also includes the compact hash samples used for comparison.

### Compare two workbooks

```sh
xldiff compare model_v1.xlsx model_v2.xlsx
xldiff compare model_v1.xlsx model_v2.xlsx --json
```

The report separates sheet-name overlap, formula overlap, value overlap, and
the combined `score`. Each available overlap ranges from 0 to 1.
JSON uses `null` when both workbooks lack the corresponding formula or value
content. Text output uses `-` for that result.

If numbers change but formulas stay the same, `values` can fall while `formulas`
and `score` remain high. If formulas change, `formulas` and `score` can fall
even when stored values remain similar. The report does not identify changed
cells or prove that two formulas have the same meaning.

### Review a version sequence with lineage

```sh
xldiff lineage models --keep 5
xldiff lineage models --recursive --keep 5 --pivot 0.6 --json
xldiff lineage model_v1.xlsx model_v2.xlsm
```

Each path can be a workbook or a directory. Discovery is nonrecursive unless
you pass `--recursive`. It skips Excel lock files whose names start with `~$`.

The report marks readable versions as `keep` or `drop`. These are selection
suggestions. Neither action changes a file. Unreadable inputs have
`decision: "review"` and `reason: "unreadable"` in JSON. They remain in the
report even when every input is unreadable. Their absence from the JSON `keep`
list does not make them safe to discard.

`--keep` must be a positive integer. `--pivot` must be a finite number between
0 and 1, inclusive. The defaults, 5 and 0.6, are conventions rather than
validated deletion criteria. The Python `lineage` API raises `ValueError` for
invalid selection values. The CLI reports a usage error.

### JSON, cache, help, and exit codes

All three subcommands accept `--json` and `--cache FILE`:

```sh
xldiff fingerprint model_v1.xlsx --cache fingerprints.json --json
xldiff compare model_v1.xlsx model_v2.xlsx --cache fingerprints.json
xldiff lineage models --cache fingerprints.json --json
xldiff --help
xldiff fingerprint --help
xldiff compare --help
xldiff lineage --help
```

`fingerprint --json` returns a list of fingerprints. `compare --json` returns
the two paths and the comparison results. `lineage --json` returns `versions`
and a `keep` list. Inspect each version's decision and error before using JSON
in another program. Do not use the `keep` list as deletion authority.

The cache stores fingerprints keyed by path, file size, and modification time.
The CLI rejects a cache destination that would overwrite an input workbook,
including an alias to the same existing file. Use a separate JSON destination.
A changed workbook with the same size and modification time can produce a
stale cache hit. Omit `--cache` for a fresh read. Cache files include paths,
sheet names, counts, and hashes. Keep them private when that metadata is private.

Exit code 0 means the command completed without unreadable inputs. Code 1 means
at least one input was unreadable. Code 2 means a usage error, including invalid
selection options or no discovered inputs. Readable inputs still appear in a
report when another input cannot be read. Similarity results involving an
unreadable workbook are not evidence of similarity.

## How comparison works

The tool represents each workbook with two sets:

- Formulas use the sheet name and normalized formula text. Relative A1 references
  become offsets from the formula cell. References with `$` retain their absolute
  row or column. Repeated normalized formulas on a sheet become one set item.
- Values use the sheet name, column, and stored text. These include numbers,
  strings, booleans, and cached formula results when present. Repeated identical
  values in the same column become one set item.

An inserted row can leave these sets unchanged when formulas move with the data.
An inserted column changes the column component of value items. This can reduce
value overlap even if the underlying data stays the same.

The tool retains up to 256 smallest 64-bit BLAKE2b hashes per set. It estimates
overlap from the smallest hashes in the union of two samples. If the full sets
together contain at most 256 distinct hashes, the hash-set overlap is exact.
For larger sets, the estimate can miss small changes. Hash overlap still does
not establish byte identity or complete workbook equivalence.

Sheet overlap is the number of shared sheet names divided by the number of
distinct sheet names across both files. The combined score uses this rule:

```text
0.3 * sheets + 0.7 * formulas    if either workbook has formulas
0.3 * sheets + 0.7 * values      otherwise, if either has values
sheets                         otherwise
```

The weights and sample size are implementation conventions. They are not
calibrated measures of business importance. When formulas exist, the combined
score excludes value overlap. Read `values` separately when changed numbers
matter to your review.

## How version ordering and selection work

The tool reads filename tokens such as `v1`, `v2.3`, `v2_3`, and `V10`.
The last version token wins. It also recognizes dates such as `2026-01-30`,
`30-01-2026`, and `20260130`. It orders readable files by version token, then
filename date, then modification time.

Mixed naming schemes can produce a misleading sequence. A date-only filename
sorts before a filename with a version token, even if its date is later.
Modification time is a tie-breaker, not proof of authorship or chronology.
Use one naming scheme for one model, and check the reported order.

Matching version and date tokens, or matching filename stems when neither
exists, identify possible copies. Within such a group, xldiff collapses only
files with identical bytes. Different contents remain separate entries, even
when their filenames contain the same version number. Equal similarity scores
do not collapse files. Copy markers such as `copy` or `(1)` have no special
meaning. A single entry can represent multiple byte-identical copies.

Consecutive readable versions are compared. A score below `--pivot` marks a
pivot, which means a change crossed the selected threshold. Selection keeps
the newest readable version and the readable version before each pivot.
It fills remaining places from newest to oldest, up to `--keep`.
If there are too many pivots, the newest version and the steepest drops take
priority. Unreadable inputs sort first by name and require separate review.

## Limits

- Styling, charts, macros, defined names, comments, and pivot caches are ignored.
  Differences in these parts can matter even when xldiff reports full overlap.
- The XML reader and formula normalizer use regular expressions, not a complete
  spreadsheet parser. Unusual XML layouts or formula syntax can be misread.
  An A1-shaped token inside a formula string literal can be rewritten as a
  reference. Cells without explicit cell references are skipped.
- Shared-formula continuation cells are not expanded from their master formula.
  The tool cannot guarantee complete formula coverage.
- Formula values come from saved cached results. Results can be missing or stale.
  xldiff does not calculate them or check their freshness.
- Set comparison discards repetition and much cell-position information. A high
  score can hide a material change. This is not a cell-by-cell diff.
- Filename parsing cannot establish the true history of a model. A folder with
  unrelated models does not become a meaningful lineage because the tool orders it.

## Updates

Check the [GitHub releases](https://github.com/Fergonz1993/xldiff/releases) and
[changelog](CHANGELOG.md). For a newer version, use that release's exact wheel
URL with `python -m pip install --upgrade "WHEEL_URL"` in your virtual
environment. If you use uv, use `uv tool install --force "WHEEL_URL"`.
Replace `WHEEL_URL` with the full URL from that release. Check `xldiff --version`
after the update. Do not use a package-index lookup or `pip install --upgrade
xldiff` to update this project.

## Contributions and license

This repository does not accept pull requests, issues, or discussions.
No support or response is promised. There is no alternative contact route for
submissions. You remain free to use, modify, and fork the code under the
[MIT license](LICENSE). See [CONTRIBUTING.md](CONTRIBUTING.md) for the policy
and [the maintainer guide](docs/MAINTAINING.md) for owner procedures.
