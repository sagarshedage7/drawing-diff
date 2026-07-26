"""End-to-end comparison over generated sample drawings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drawingdiff import compare_drawings                      # noqa: E402
from drawingdiff.models import FindingKind, Severity          # noqa: E402
from drawingdiff.report import to_annotated_pdf, to_json, to_text  # noqa: E402
from tools.make_samples import make_pair                      # noqa: E402


@pytest.fixture(scope="module")
def samples(tmp_path_factory) -> tuple[Path, Path]:
    return make_pair(tmp_path_factory.mktemp("samples"))


@pytest.fixture(scope="module")
def result(samples):
    old, new = samples
    return compare_drawings(old, new, dpi=150)


def test_self_comparison_finds_nothing(samples):
    """A drawing compared against itself must be clean — the false-positive check."""
    old, _ = samples
    result = compare_drawings(old, old, dpi=150)
    assert result.findings == [], result.sorted_findings()[:5]


def test_dimension_change_detected(result):
    changes = [f for f in result.findings
               if f.kind is FindingKind.DIMENSION_CHANGED]
    assert any(f.old_value == "360" and f.new_value == "365" for f in changes), \
        [f.message for f in changes]


def test_tolerance_change_detected(result):
    changes = [f for f in result.findings
               if f.kind is FindingKind.TOLERANCE_CHANGED]
    assert changes, "expected the ±0.1 -> ±0.05 change"
    assert all(f.severity is Severity.CRITICAL for f in changes)


def test_note_added_and_removed(result):
    added = {f.new_value for f in result.findings
             if f.kind is FindingKind.TEXT_ADDED}
    removed = {f.old_value for f in result.findings
               if f.kind is FindingKind.TEXT_REMOVED}
    assert any("ZINC PLATE" in (v or "") for v in added), added
    assert any("TOLERANCES" in (v or "") for v in removed), removed


def test_added_geometry_detected(result):
    geometry = [f for f in result.findings
                if f.kind is FindingKind.GEOMETRY_CHANGED]
    assert geometry, "the extra hole should show up in the raster pass"
    # The added hole sits around (300, 180) in points.
    assert any(f.bbox.x0 <= 300 <= f.bbox.x1 and f.bbox.y0 <= 180 <= f.bbox.y1
               for f in geometry), [f.bbox for f in geometry]


def test_findings_are_sorted_worst_first(result):
    severities = [f.severity for f in result.sorted_findings()]
    assert severities == sorted(severities)


def test_determinism(samples):
    """Identical inputs must give byte-identical JSON."""
    old, new = samples
    first = compare_drawings(old, new, dpi=150).to_dict()
    second = compare_drawings(old, new, dpi=150).to_dict()
    assert first == second


def test_ignore_region_suppresses_findings(samples):
    """Masking the title block should drop the revision-letter finding."""
    old, new = samples
    from drawingdiff.models import BBox

    title_block = BBox(560, 480, 825, 580)
    baseline = compare_drawings(old, new, dpi=150)
    masked = compare_drawings(old, new, dpi=150, ignore=[title_block])
    assert len(masked.findings) <= len(baseline.findings)


def test_no_raster_is_text_only(samples):
    old, new = samples
    result = compare_drawings(old, new, dpi=150, skip_raster=True)
    assert all(f.kind is not FindingKind.GEOMETRY_CHANGED for f in result.findings)
    assert any(f.kind is FindingKind.DIMENSION_CHANGED for f in result.findings)


def test_reports_render(result, tmp_path):
    text = to_text(result)
    assert "Findings:" in text
    assert "Critical" in text

    json_path = to_json(result, tmp_path / "result.json")
    assert json_path.exists() and json_path.stat().st_size > 0

    pdf_path = to_annotated_pdf(result, tmp_path / "annotated.pdf")
    assert pdf_path.exists() and pdf_path.stat().st_size > 0


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        compare_drawings("does_not_exist.pdf", "also_missing.pdf")
