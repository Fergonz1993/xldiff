from __future__ import annotations

from xldiff.fingerprint import fingerprint
from xldiff.similarity import jaccard, similarity, sketch_jaccard


def test_identical_copies_score_one(tmp_path, make_workbook, formulas, data):
    sheets = {"Inputs": data(rows=10), "Cashflow": formulas(rows=30)}
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", sheets))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", sheets))

    sim = similarity(a, b)

    assert (sim.sheets, sim.formulas, sim.values, sim.score) == (1.0, 1.0, 1.0, 1.0)


def test_inserting_a_row_in_the_middle_of_a_block_changes_nothing(tmp_path, make_workbook, formulas):
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": formulas(rows=30)}))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", {"Cashflow": formulas(rows=30, gap_after=15)}))

    sim = similarity(a, b)

    assert sim.formulas == 1.0  # R1C1 offsets are unchanged by the shift
    assert sim.values == 1.0  # value items are anchored on the column, not the row
    assert sim.score == 1.0


def test_inserting_a_row_above_a_block_changes_nothing(tmp_path, make_workbook, formulas):
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": formulas(rows=30, start_row=1)}))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", {"Cashflow": formulas(rows=30, start_row=2)}))

    assert similarity(a, b).score == 1.0


def test_inserting_a_column_lowers_values_but_not_formulas(tmp_path, make_workbook, formulas):
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": formulas(rows=30, first_column=1)}))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", {"Cashflow": formulas(rows=30, first_column=2)}))

    sim = similarity(a, b)

    assert sim.formulas == 1.0
    assert sim.values == 0.0  # every value item moved to a different column letter
    assert sim.score == 1.0


def test_rewriting_the_formulas_of_one_sheet_drops_the_formula_estimate(tmp_path, make_workbook, formulas, data):
    before = {
        "Inputs": data(rows=5),
        "Cashflow": formulas(rows=40),
        "Summary": formulas(rows=5, base=900, factor=500),
    }
    after = dict(before, Cashflow=formulas(rows=40, template="SUM({col}${first}:{col}{row})*{factor}"))
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", before))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", after))

    sim = similarity(a, b)

    assert sim.sheets == 1.0
    assert sim.formulas < 0.2
    assert sim.score < 0.6


def test_changing_only_the_numbers_keeps_the_formulas_identical(tmp_path, make_workbook, formulas, data):
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Data": data(rows=30, base=100), "Cashflow": formulas(rows=20)}))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", {"Data": data(rows=30, base=500), "Cashflow": formulas(rows=20)}))

    sim = similarity(a, b)

    assert sim.formulas == 1.0
    assert sim.values < 0.6
    assert sim.score == 1.0  # the score is formula-first; read `values` when the data is what matters


def test_workbooks_without_formulas_fall_back_to_values(tmp_path, make_workbook, data):
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Data": data(rows=40, base=100)}))
    same = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", {"Data": data(rows=40, base=100)}))
    other = fingerprint(make_workbook(tmp_path / "sample_v3.xlsx", {"Data": data(rows=40, base=900, label="row")}))

    identical = similarity(a, same)
    different = similarity(a, other)

    assert identical.formulas is None and different.formulas is None
    assert identical.values == 1.0 and identical.score == 1.0
    assert different.values == 0.0
    assert different.score == 0.3  # sheet names still match, nothing else does
    assert different.score < identical.score


def test_one_sided_and_empty_comparisons():
    assert sketch_jaccard([], []) is None
    assert sketch_jaccard([1, 2], []) == 0.0
    assert sketch_jaccard([], [1, 2]) == 0.0
    assert sketch_jaccard([1, 2, 3], [1, 2, 3]) == 1.0
    assert sketch_jaccard([1, 2, 3, 4], [3, 4, 5, 6]) == 2 / 6  # exact Jaccard while both sketches fit under k
    assert sketch_jaccard([1, 2, 3, 4], [3, 4, 5, 6], k=2) == 0.0  # only the two smallest hashes are compared
    assert jaccard([], []) == 1.0
    assert jaccard(["Inputs"], []) == 0.0


def test_score_falls_back_to_sheet_overlap_when_there_is_no_content(tmp_path, make_workbook):
    a = fingerprint(make_workbook(tmp_path / "sample_v1.xlsx", {"Inputs": [], "Cashflow": []}))
    b = fingerprint(make_workbook(tmp_path / "sample_v2.xlsx", {"Inputs": [], "Summary": []}))

    sim = similarity(a, b)

    assert (sim.formulas, sim.values) == (None, None)
    assert sim.sheets == sim.score == 1 / 3
