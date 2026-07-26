"""Text-layer comparison, driven by hand-built spans (no PDF needed)."""

from __future__ import annotations

from drawingdiff.models import BBox, FindingKind, Severity, TextSpan
from drawingdiff.textdiff import compare_text


def span(text: str, x: float = 100.0, y: float = 100.0) -> TextSpan:
    return TextSpan(text=text, bbox=BBox(x, y, x + 40, y + 10), page=0)


def kinds(findings):
    return [f.kind for f in findings]


def test_identical_pages_produce_nothing():
    spans = [span("50"), span("NOTES", 200, 300)]
    assert compare_text(spans, list(spans), page=0) == []


def test_dimension_change_is_critical():
    findings = compare_text([span("360")], [span("365")], page=0)
    assert len(findings) == 1
    assert findings[0].kind is FindingKind.DIMENSION_CHANGED
    assert findings[0].severity is Severity.CRITICAL
    assert findings[0].old_value == "360"
    assert findings[0].new_value == "365"


def test_tolerance_change_is_critical():
    findings = compare_text([span("Ø90 ±0.1")], [span("Ø90 ±0.05")], page=0)
    assert FindingKind.TOLERANCE_CHANGED in kinds(findings)
    assert all(f.severity is Severity.CRITICAL for f in findings)


def test_value_and_tolerance_both_change():
    findings = compare_text([span("50 ±0.1")], [span("55 ±0.05")], page=0)
    assert FindingKind.DIMENSION_CHANGED in kinds(findings)
    assert FindingKind.TOLERANCE_CHANGED in kinds(findings)


def test_added_and_removed_text():
    old = [span("NOTE ONE", 100, 100)]
    new = [span("NOTE TWO", 400, 400)]
    findings = compare_text(old, new, page=0)
    assert FindingKind.TEXT_REMOVED in kinds(findings)
    assert FindingKind.TEXT_ADDED in kinds(findings)


def test_prose_change_is_major_not_critical():
    findings = compare_text(
        [span("MATERIAL: STEEL")], [span("MATERIAL: ALUMINIUM")], page=0
    )
    assert findings[0].kind is FindingKind.TEXT_CHANGED
    assert findings[0].severity is Severity.MAJOR


def test_small_move_still_counts_as_the_same_span():
    findings = compare_text([span("50", 100, 100)], [span("55", 101, 101)], page=0)
    assert findings[0].kind is FindingKind.DIMENSION_CHANGED


def test_pure_move_is_not_reported():
    """Same text, far away — matched by content, so no add/remove noise."""
    findings = compare_text([span("50", 100, 100)], [span("50", 500, 500)], page=0)
    assert findings == []


def test_whitespace_only_change_is_ignored():
    findings = compare_text([span("Ø 90")], [span("Ø  90")], page=0)
    assert findings == []


def test_ordering_is_deterministic():
    old = [span("50", 100, 100), span("OLD NOTE", 200, 200), span("Ø20", 300, 300)]
    new = [span("55", 100, 100), span("NEW NOTE", 200, 200), span("Ø25", 300, 300)]
    first = compare_text(old, new, page=0)
    second = compare_text(list(reversed(old)), list(reversed(new)), page=0)
    assert sorted(first) == sorted(second)


def test_critical_sorts_before_major():
    old = [span("50", 100, 100), span("MATERIAL: STEEL", 200, 200)]
    new = [span("55", 100, 100), span("MATERIAL: BRASS", 200, 200)]
    findings = sorted(compare_text(old, new, page=0))
    assert findings[0].severity is Severity.CRITICAL
