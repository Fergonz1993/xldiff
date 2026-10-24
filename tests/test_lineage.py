from __future__ import annotations

import zipfile
import shutil

from xldiff.lineage import group_versions, lineage, parse_date, parse_version


def model(index, formulas, data, template="{col}{row}*{factor}"):
    """One version of a small model: inputs, a formula sheet that grows, and a stable summary."""
    return {
        "Inputs": data(rows=4 + index),
        "Cashflow": formulas(rows=40 + index, template=template),
        "Summary": formulas(rows=5, base=900, factor=500),
    }


REWRITE = "SUM({col}${first}:{col}{row})*{factor}"


def test_version_tokens():
    assert parse_version("model_v1.xlsx") == (1,)
    assert parse_version("Acme Model v2.3.xlsx") == (2, 3)
    assert parse_version("Acme Model v2_3.xlsx") == (2, 3)
    assert parse_version("Acme Model V10.xlsx") == (10,)
    assert parse_version("Acme Model final.xlsx") == ()
    assert parse_version("revision5.xlsx") == ()  # the v has to start the token
    assert parse_version("dir_v9/Acme Model.xlsx") == ()  # only the file name is read


def test_dates_in_names():
    assert parse_date("Acme Model 2026-01-30.xlsx") == 20260130
    assert parse_date("Acme Model 30-01-2026.xlsx") == 20260130
    assert parse_date("Acme Model 20260130.xlsx") == 20260130
    assert parse_date("Acme Model 2026.01.30.xlsx") == 20260130
    assert parse_date("Acme Model v3.xlsx") == 0
    assert parse_date("Acme Model 99-99-2026.xlsx") == 0  # not a date


def test_files_of_the_same_version_are_one_version(tmp_path, make_workbook, data):
    a = make_workbook(tmp_path / "Acme Model v2.3.xlsx", {"Data": data(rows=3)})
    (tmp_path / "backup").mkdir()
    b = tmp_path / "backup" / "Acme Model v2_3.xlsx"
    shutil.copyfile(a, b)

    groups = group_versions([a, b])

    assert len(groups) == 1
    assert len(lineage([a, b])) == 1


def test_ordering_runs_over_versions_then_dates(tmp_path, make_workbook, data):
    names = [
        "Acme Model V10.xlsx",
        "Acme Model 20260315.xlsx",
        "Acme Model.xlsx",
        "Acme Model v2.3.xlsx",
        "Acme Model 2026-01-30.xlsx",
        "Acme Model 28-02-2026.xlsx",
    ]
    paths = [make_workbook(tmp_path / name, {"Data": data(rows=3)}) for name in names]

    versions = lineage(paths, keep=10)

    assert [v.label for v in versions] == ["Acme Model", "20260130", "20260228", "20260315", "v2.3", "v10"]


def test_eight_versions_with_a_rewrite_at_v5(tmp_path, make_workbook, formulas, data):
    paths = [
        make_workbook(
            tmp_path / f"model_v{i}.xlsx",
            model(i, formulas, data, template=REWRITE if i >= 5 else "{col}{row}*{factor}"),
        )
        for i in range(1, 9)
    ]

    versions = lineage(paths, keep=5)

    assert [v.label for v in versions] == [f"v{i}" for i in range(1, 9)]
    assert versions[4].sim_prev < 0.6  # v5 rewrote the model
    assert all(v.sim_prev > 0.9 for v in versions[1:] if v.label != "v5")
    assert [v.reason for v in versions] == [
        "dropped",
        "dropped",
        "dropped",
        "before pivot",
        "fill",
        "fill",
        "fill",
        "newest",
    ]
    assert [v.path for v in versions if v.decision == "keep"] == [str(p) for p in paths[3:]]


def test_a_short_lineage_keeps_everything(tmp_path, make_workbook, formulas, data):
    paths = [make_workbook(tmp_path / f"model_v{i}.xlsx", model(i, formulas, data)) for i in range(1, 4)]

    versions = lineage(paths, keep=5)

    assert [v.decision for v in versions] == ["keep", "keep", "keep"]
    assert [v.reason for v in versions] == ["fill", "fill", "newest"]


def test_more_pivots_than_budget_keeps_the_steepest_drops(tmp_path, make_workbook, formulas, data):
    paths = [
        make_workbook(tmp_path / f"model_v{i}.xlsx", model(i, formulas, data, template=f"ROUND({{col}}{{row}}*{{factor}}, {i})"))
        for i in range(1, 9)
    ]

    versions = lineage(paths, keep=5)

    assert all(v.sim_prev < 0.6 for v in versions[1:])  # every version rewrote the formulas
    kept = [v for v in versions if v.decision == "keep"]
    assert len(kept) == 5
    assert versions[-1].reason == "newest"
    assert {v.reason for v in kept} == {"newest", "before pivot"}


def test_unreadable_files_sort_first_and_require_review(tmp_path, make_workbook, formulas, data):
    paths = [make_workbook(tmp_path / f"model_v{i}.xlsx", model(i, formulas, data)) for i in range(1, 4)]
    broken = tmp_path / "model_v9.xlsx"
    broken.write_text("not a workbook at all")

    versions = lineage([*paths, broken], keep=5)

    assert versions[0].path == str(broken)  # nothing can be said about where it belongs
    assert (versions[0].decision, versions[0].reason) == ("review", "unreadable")
    assert versions[0].sim_prev is None
    assert versions[-1].reason == "newest"
    assert [v.decision for v in versions[1:]] == ["keep", "keep", "keep"]


def test_a_lineage_of_only_unreadable_files_requires_review(tmp_path):
    first = tmp_path / "model_v1.xlsx"
    second = tmp_path / "model_v2.xlsx"
    first.write_text("not a workbook")
    with zipfile.ZipFile(second, "w") as archive:
        archive.writestr("notes.txt", "not a workbook either")

    versions = lineage([second, first], keep=5)

    assert [v.path for v in versions] == [str(first), str(second)]
    assert [(v.decision, v.reason) for v in versions] == [("review", "unreadable"), ("review", "unreadable")]
    assert versions[-1].fingerprint.error is not None


def test_an_empty_lineage_is_empty():
    assert lineage([]) == []


def test_same_version_with_different_contents_preserves_both(tmp_path, make_workbook, data):
    a = make_workbook(tmp_path / "model_v3.xlsx", {"Data": data(rows=3)})
    other = tmp_path / "other"
    other.mkdir()
    b = make_workbook(other / "model_v3.xlsx", {"Data": data(rows=3, base=999)})
    assert {entry.path for entry in lineage([a, b])} == {str(a), str(b)}


def test_invalid_selection_parameters_fail():
    import pytest

    for keep, pivot in [(0, 0.6), (-1, 0.6), (5, -0.1), (5, 1.1), (5, float("nan"))]:
        with pytest.raises(ValueError):
            lineage([], keep=keep, pivot=pivot)
