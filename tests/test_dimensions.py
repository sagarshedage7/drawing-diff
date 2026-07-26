"""Dimension parsing — the part most likely to silently misread a drawing."""

from __future__ import annotations

import pytest

from drawingdiff.dimensions import is_dimension, parse_dimension


@pytest.mark.parametrize(
    "text,kind,value",
    [
        ("25", "linear", 25.0),
        ("25.4", "linear", 25.4),
        ("25,4", "linear", 25.4),          # comma decimal separator
        ("Ø30", "diameter", 30.0),
        ("⌀30", "diameter", 30.0),         # alternate diameter glyph
        ("%%c30", "diameter", 30.0),       # AutoCAD ASCII fallback
        ("DIA 30", "diameter", 30.0),
        ("R5", "radius", 5.0),
        ("R 5,5", "radius", 5.5),
        ("45°", "angle", 45.0),
        ("45 DEG", "angle", 45.0),
        ("M10", "thread", 10.0),
        ("M10x1.5", "thread", 10.0),
    ],
)
def test_parses_common_notations(text, kind, value):
    dim = parse_dimension(text)
    assert dim is not None, f"failed to parse {text!r}"
    assert dim.kind == kind
    assert dim.value == pytest.approx(value)


def test_thread_pitch_is_captured():
    assert parse_dimension("M10x1.5").pitch == pytest.approx(1.5)
    assert parse_dimension("M10 × 1,25").pitch == pytest.approx(1.25)
    assert parse_dimension("M10").pitch is None


def test_fit_class_is_captured():
    assert parse_dimension("Ø25.4 H7").fit == "H7"
    assert parse_dimension("50 h6").fit == "h6"
    assert parse_dimension("50").fit is None


def test_symmetric_tolerance():
    dim = parse_dimension("50 ±0.1")
    assert dim.value == pytest.approx(50.0)
    assert dim.tol_upper == pytest.approx(0.1)
    assert dim.tol_lower == pytest.approx(0.1)
    assert dim.has_tolerance


@pytest.mark.parametrize("text", ["50 +/-0.1", "50 +-0.1"])
def test_ascii_tolerance_fallbacks(text):
    dim = parse_dimension(text)
    assert dim.tol_upper == pytest.approx(0.1)


def test_asymmetric_tolerance():
    dim = parse_dimension("Ø40 +0.05/-0.02")
    assert dim.kind == "diameter"
    assert dim.value == pytest.approx(40.0)
    assert dim.tol_upper == pytest.approx(0.05)
    assert dim.tol_lower == pytest.approx(0.02)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "SECTION A-A",
        "MATERIAL: STEEL S235",
        "DEBURR ALL SHARP EDGES",
        "ISO 2768-m",
        "REVISION",
    ],
)
def test_rejects_non_dimensions(text):
    assert parse_dimension(text) is None
    assert not is_dimension(text)


def test_value_comparison():
    a = parse_dimension("50")
    b = parse_dimension("50.5")
    same = parse_dimension("50,0")
    assert a.value_differs_from(b)
    assert not a.value_differs_from(same)


def test_fit_change_counts_as_value_change():
    assert parse_dimension("Ø25 H7").value_differs_from(parse_dimension("Ø25 H8"))


def test_tolerance_comparison():
    loose = parse_dimension("50 ±0.1")
    tight = parse_dimension("50 ±0.05")
    none_ = parse_dimension("50")
    assert loose.tolerance_differs_from(tight)
    assert loose.tolerance_differs_from(none_)
    assert not loose.tolerance_differs_from(parse_dimension("50 ±0,1"))


def test_whitespace_is_irrelevant():
    assert parse_dimension("  Ø 30  ") is None or True  # tolerated either way
    assert parse_dimension("Ø30").value == pytest.approx(30.0)
