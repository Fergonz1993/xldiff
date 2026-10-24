from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[1] / "src")


def run(*args, expect=0):
    result = subprocess.run(
        [sys.executable, "-m", "xldiff", *[str(a) for a in args]],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": SRC},
    )
    assert result.returncode == expect, f"exit {result.returncode}\n{result.stdout}\n{result.stderr}"
    return result


def model(index, formulas, data, template="{col}{row}*{factor}"):
    return {
        "Inputs": data(rows=4 + index),
        "Cashflow": formulas(rows=40 + index, template=template),
        "Summary": formulas(rows=5, base=900, factor=500),
    }


REWRITE = "SUM({col}${first}:{col}{row})*{factor}"


def eight_versions(directory, make_workbook, formulas, data):
    return [
        make_workbook(
            directory / f"model_v{i}.xlsx",
            model(i, formulas, data, template=REWRITE if i >= 5 else "{col}{row}*{factor}"),
        )
        for i in range(1, 9)
    ]


def test_fingerprint_prints_a_table_and_json(tmp_path, make_workbook, formulas, data, formula_values_cached):
    path = make_workbook(tmp_path / "sample_v1.xlsx", {"Inputs": data(rows=5), "Cashflow": formulas(rows=20)})

    table = run("fingerprint", path).stdout
    assert "Cashflow" in table and "formulas" in table and "bottom-256" in table

    payload = json.loads(run("fingerprint", path, "--json").stdout)
    assert len(payload) == 1
    assert payload[0]["sheets"]["Cashflow"] == {"cells": 40, "formulas": 20, "values": 40 if formula_values_cached else 20}
    assert len(payload[0]["formula_sketch"]) == 20
    assert payload[0]["error"] is None


def test_compare_prints_every_component(tmp_path, make_workbook, formulas, data):
    a = make_workbook(tmp_path / "sample_v1.xlsx", model(1, formulas, data))
    b = make_workbook(tmp_path / "sample_v2.xlsx", model(1, formulas, data, template=REWRITE))

    text = run("compare", a, b).stdout
    assert "score" in text and "formulas" in text

    payload = json.loads(run("compare", a, b, "--json").stdout)
    assert payload["a"] == str(a) and payload["b"] == str(b)
    assert payload["sheets"] == 1.0
    assert payload["score"] < 0.6
    assert set(payload) == {"a", "b", "sheets", "formulas", "values", "score"}


def test_lineage_reports_the_timeline_and_the_keep_list(tmp_path, make_workbook, formulas, data):
    paths = eight_versions(tmp_path, make_workbook, formulas, data)

    text = run("lineage", *paths).stdout
    assert "8 versions, keeping 5" in text
    assert "PIVOT" in text
    assert text.count("KEEP") == 5

    payload = json.loads(run("lineage", *paths, "--json").stdout)
    assert payload["keep"] == [str(p) for p in paths[3:]]
    assert [v["reason"] for v in payload["versions"]][-1] == "newest"
    assert "formula_sketch" not in payload["versions"][0]["fingerprint"]
    assert payload["versions"][0]["fingerprint"]["sheets"]["Cashflow"]["formulas"] == 41


def test_lineage_scans_directories(tmp_path, make_workbook, formulas, data):
    nested = tmp_path / "archive"
    nested.mkdir()
    make_workbook(tmp_path / "model_v1.xlsx", model(1, formulas, data))
    make_workbook(nested / "model_v2.xlsx", model(2, formulas, data))
    (tmp_path / "~$model_v3.xlsx").write_text("an Excel lock file")

    flat = json.loads(run("lineage", tmp_path, "--json").stdout)
    deep = json.loads(run("lineage", tmp_path, "--recursive", "--json").stdout)

    assert len(flat["versions"]) == 1
    assert len(deep["versions"]) == 2


def test_keep_and_pivot_are_configurable(tmp_path, make_workbook, formulas, data):
    paths = eight_versions(tmp_path, make_workbook, formulas, data)

    payload = json.loads(run("lineage", *paths, "--keep", "2", "--json").stdout)

    assert [v["reason"] for v in payload["versions"]] == [
        "dropped",
        "dropped",
        "dropped",
        "before pivot",
        "dropped",
        "dropped",
        "dropped",
        "newest",
    ]
    assert len(payload["keep"]) == 2


def test_unreadable_input_exits_one_and_still_reports_the_rest(tmp_path, make_workbook, formulas, data):
    good = make_workbook(tmp_path / "model_v1.xlsx", model(1, formulas, data))
    broken = tmp_path / "model_v2.xlsx"
    broken.write_text("not a workbook")
    empty = tmp_path / "model_v3.xlsx"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("notes.txt", "nothing here")

    prints = run("fingerprint", good, broken, empty, expect=1).stdout
    assert "unreadable" in prints and "Cashflow" in prints

    timeline = run("lineage", good, broken, empty, expect=1).stdout
    assert "unreadable" in timeline and "KEEP" in timeline

    payload = json.loads(run("lineage", good, broken, empty, "--json", expect=1).stdout)
    assert payload["keep"] == [str(good)]


def test_usage_errors_exit_two(tmp_path):
    assert subprocess.run([sys.executable, "-m", "xldiff"], capture_output=True, env={**os.environ, "PYTHONPATH": SRC}).returncode == 2
    run("lineage", tmp_path, expect=2)  # a directory with no workbooks in it


def test_cache_is_written_and_reused(tmp_path, make_workbook, formulas, data):
    path = make_workbook(tmp_path / "sample_v1.xlsx", {"Cashflow": formulas(rows=20)})
    cache_file = tmp_path / "cache.json"

    first = json.loads(run("fingerprint", path, "--cache", cache_file, "--json").stdout)
    assert cache_file.exists()
    (key,) = json.loads(cache_file.read_text())

    cached = json.loads(cache_file.read_text())
    cached[key]["sheets"] = {"Sentinel": {"cells": 1, "formulas": 1, "values": 1}}
    cache_file.write_text(json.dumps(cached))
    second = json.loads(run("fingerprint", path, "--cache", cache_file, "--json").stdout)

    assert list(first[0]["sheets"]) == ["Cashflow"]
    assert list(second[0]["sheets"]) == ["Sentinel"]  # served from the cache, the file was not read again


def test_cache_cannot_overwrite_an_input(tmp_path, make_workbook, data):
    path = make_workbook(tmp_path / "model.xlsx", {"Data": data(rows=2)})
    before = path.read_bytes()
    run("fingerprint", path, "--cache", path, expect=2)
    assert path.read_bytes() == before
    alias = tmp_path / "cache.json"
    alias.symlink_to(path)
    run("lineage", path, "--cache", alias, expect=2)
    assert path.read_bytes() == before
    hardlink = tmp_path / "hardlink.json"
    hardlink.hardlink_to(path)
    run("compare", path, path, "--cache", hardlink, expect=2)
    assert path.read_bytes() == before


def test_invalid_selection_options_are_usage_errors(tmp_path, make_workbook, data):
    path = make_workbook(tmp_path / "model.xlsx", {"Data": data(rows=2)})
    for option, value in [("--keep", "0"), ("--keep", "-1"), ("--pivot", "nan"), ("--pivot", "2")]:
        result = run("lineage", path, option, value, expect=2)
        assert f"{option} must" in result.stderr
