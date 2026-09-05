from __future__ import annotations

import zipfile

from xldiff.fingerprint import (
    Fingerprint,
    SheetStats,
    bottom_k,
    fingerprint,
    fingerprint_cached,
    load_cache,
    r1c1,
    save_cache,
    scan_sheet,
)


def test_sheet_stats_count_cells_formulas_and_values(tmp_path, make_workbook, formulas, data):
    path = make_workbook(tmp_path / "sample_v1.xlsx", {"Inputs": data(rows=5), "Cashflow": formulas(rows=20)})

    fp = fingerprint(path)

    assert fp.error is None
    assert set(fp.sheets) == {"Inputs", "Cashflow"}
    assert fp.sheets["Inputs"] == SheetStats(cells=10, formulas=0, values=10)
    # 20 data cells + 20 formula cells; the factor varies per row, so all 20 formulas are distinct in R1C1.
    assert fp.sheets["Cashflow"].cells == 40
    assert fp.sheets["Cashflow"].formulas == 20
    # openpyxl writes no cached result for a formula cell, so only the data column counts as a value.
    assert fp.sheets["Cashflow"].values == 20
    assert fp.total_cells == 50
    assert len(fp.formula_sketch) == 20
    assert len(fp.value_sketch) == 30
    assert fp.size > 0


def test_r1c1_keeps_absolute_references_absolute():
    assert r1c1("=A1", col=3, row=3) == "=R[-2]C[-2]"
    assert r1c1("=$A$1", col=3, row=3) == "=R1C1"
    assert r1c1("=A$1", col=3, row=3) == "=R1C[-2]"
    assert r1c1("=$A1", col=3, row=3) == "=R[-2]C1"
    assert r1c1("=A1", col=3, row=3) != r1c1("=$A$1", col=3, row=3)
    assert r1c1("=SUM($B$2:B10)", col=2, row=5) == "=SUM(R2C2:R[5]C[0])"


def test_r1c1_leaves_function_names_and_exponents_alone():
    assert r1c1("=LOG10(A1)", col=1, row=1) == "=LOG10(R[0]C[0])"
    assert r1c1("=1.5E10*A1", col=1, row=1) == "=1.5E10*R[0]C[0]"


def test_a_formula_filled_down_a_column_is_one_distinct_formula(tmp_path, make_workbook, formulas):
    rows = formulas(rows=30, factor=2, template="{col}{row}*2")

    fp = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": rows}))

    assert fp.sheets["Cashflow"].cells == 60
    assert fp.sheets["Cashflow"].formulas == 1


def test_shared_strings_resolve_to_their_text(tmp_path, make_workbook):
    path = make_workbook(tmp_path / "sample_v1.xlsx", {"Inputs": [["widget"], [42]]})

    fp = fingerprint(path)

    assert bottom_k({"Inputs|A|widget"})[0] in fp.value_sketch
    assert bottom_k({"Inputs|A|42"})[0] in fp.value_sketch
    assert fp.sheets["Inputs"].values == 2


def test_scan_sheet_reads_inline_strings_booleans_and_cached_results():
    xml = (
        b"<worksheet><sheetData>"
        b'<row r="1"><c r="A1" t="s"><v>0</v></c>'
        b'<c r="B1" t="inlineStr"><is><t>inline text</t></is></c></row>'
        b'<row r="2"><c r="A2"><v>42</v></c>'
        b'<c r="B2"><f>A2*2</f><v>84</v></c>'
        b'<c r="C2"/>'
        b'<c r="D2" t="b"><v>1</v></c></row>'
        b"</sheetData></worksheet>"
    )

    stats, formula_items, value_items = scan_sheet(xml, "Data", ["shared text"])

    assert stats.cells == 6
    assert stats.formulas == 1
    assert stats.values == 5  # C2 is empty and does not count
    assert formula_items == {"Data|R[0]C[-1]*2"}
    assert value_items == {
        "Data|A|shared text",
        "Data|B|inline text",
        "Data|A|42",
        "Data|B|84",  # the cached result of the formula in B2
        "Data|D|TRUE",
    }


def test_not_a_zip_is_reported_not_raised(tmp_path):
    path = tmp_path / "sample_v1.xlsx"
    path.write_text("date,amount\n2026-01-30,10\n")

    fp = fingerprint(path)

    assert fp.error is not None
    assert fp.sheets == {} and fp.formula_sketch == [] and fp.value_sketch == []
    assert fp.size > 0


def test_zip_without_a_workbook_part_is_reported(tmp_path):
    path = tmp_path / "sample_v1.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("notes.txt", "not a workbook")

    fp = fingerprint(path)

    assert fp.error == "not a workbook: xl/workbook.xml is missing"


def test_missing_file_and_unsupported_formats_are_reported(tmp_path):
    missing = fingerprint(tmp_path / "sample_v1.xlsx")
    assert "FileNotFoundError" in (missing.error or "")

    binary = tmp_path / "sample_v1.xlsb"
    binary.write_bytes(b"\x00\x01")
    assert "not supported" in (fingerprint(binary).error or "")

    legacy = tmp_path / "sample_v1.xls"
    legacy.write_bytes(b"\xd0\xcf\x11\xe0")
    assert "not supported" in (fingerprint(legacy).error or "")


def test_fingerprint_dict_round_trip(tmp_path, make_workbook, formulas):
    fp = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": formulas(rows=5)}))

    assert Fingerprint.from_dict(fp.to_dict()) == fp
    assert "formula_sketch" not in fp.summary()


def test_cache_is_keyed_by_path_size_mtime_and_is_reused(tmp_path, make_workbook, formulas):
    path = make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": formulas(rows=5)})
    cache_file = tmp_path / "cache.json"
    cache = {}

    first = fingerprint_cached(path, cache)
    save_cache(cache_file, cache)

    (key,) = cache
    assert key.endswith(f"|{path.stat().st_size}|{int(path.stat().st_mtime)}")

    reloaded = load_cache(cache_file)
    reloaded[key]["sheets"] = {"Sentinel": {"cells": 1, "formulas": 1, "values": 1}}
    second = fingerprint_cached(path, reloaded)

    assert first.sheets.keys() == {"Cashflow"}
    assert second.sheets.keys() == {"Sentinel"}  # the read came from the cache, not from the file


def test_cache_misses_when_the_file_changes(tmp_path, make_workbook, formulas):
    path = tmp_path / "sample_v1.xlsx"
    make_workbook(path, {"Cashflow": formulas(rows=5)})
    cache = {}
    fingerprint_cached(path, cache)

    make_workbook(path, {"Cashflow": formulas(rows=5), "Summary": formulas(rows=2)})
    second = fingerprint_cached(path, cache)

    assert set(second.sheets) == {"Cashflow", "Summary"}
    assert len(cache) == 2


def test_load_cache_survives_a_damaged_file(tmp_path):
    damaged = tmp_path / "cache.json"
    damaged.write_text("{not json")

    assert load_cache(damaged) == {}
    assert load_cache(tmp_path / "absent.json") == {}
