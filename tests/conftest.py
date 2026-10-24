"""Workbook builders for the tests.

No workbook is checked in: every fixture is generated with openpyxl into ``tmp_path`` and thrown away.
"""

from __future__ import annotations

import os

import pytest

from examples.workbooks import build_workbook, column_letter


def formula_rows(rows=20, start_row=1, first_column=1, base=100, factor=2, template="{col}{row}*{factor}", gap_after=None):
    """A data column and, next to it, a formula column that reads it.

    ``start_row`` and ``first_column`` move the whole block and ``gap_after`` opens an empty row inside it, which
    is what Excel does when a row or a column is inserted: everything below shifts and the formulas follow their
    operands, so the block keeps saying the same thing.
    """
    letter = column_letter(first_column)
    padding = [None] * (first_column - 1)
    out = [[] for _ in range(start_row - 1)]
    row = start_row
    for i in range(rows):
        if i == gap_after:
            out.append([])
            row += 1
        formula = "=" + template.format(col=letter, row=row, factor=factor + i, first=start_row)
        out.append(padding + [base + i, formula])
        row += 1
    return out


def data_rows(rows=20, base=100, label="item"):
    """A text column and a number column, no formulas."""
    return [[f"{label}-{i}", base + i] for i in range(rows)]


@pytest.fixture
def make_workbook():
    return build_workbook


@pytest.fixture
def formulas():
    return formula_rows


@pytest.fixture
def data():
    return data_rows


@pytest.fixture
def formula_values_cached():
    """MOG saves cached formula results; openpyxl intentionally does not."""
    return os.environ.get("XLDIFF_TEST_BACKEND") == "mog"
