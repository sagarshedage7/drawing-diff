"""Rendering a ComparisonResult as text, JSON, or an annotated PDF."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ComparisonResult, Severity

# RGB in the 0–1 range PyMuPDF expects.
_SEVERITY_COLOURS = {
    Severity.CRITICAL: (0.85, 0.10, 0.10),
    Severity.MAJOR: (0.95, 0.55, 0.05),
    Severity.MINOR: (0.20, 0.45, 0.85),
    Severity.COSMETIC: (0.55, 0.55, 0.55),
}


def to_text(result: ComparisonResult, verbose: bool = False) -> str:
    """A console summary."""
    lines: list[str] = []
    lines.append(f"Old : {result.old_path}")
    lines.append(f"New : {result.new_path}")
    lines.append(f"Pages compared: {result.pages_compared}   DPI: {result.dpi}")
    lines.append("")

    counts = result.counts_by_severity()
    total = sum(counts.values())
    lines.append(f"Findings: {total}")
    for severity in Severity:
        lines.append(f"  {severity.label:<14}{counts[severity.label]}")
    lines.append("")

    if total == 0:
        lines.append("No differences detected.")
        return "\n".join(lines)

    shown = result.sorted_findings()
    if not verbose:
        shown = [f for f in shown if f.severity <= Severity.MINOR]

    for finding in shown:
        x0, y0, x1, y1 = (round(v) for v in finding.bbox.as_tuple())
        lines.append(
            f"[{finding.severity.label:<9}] p{finding.page + 1} "
            f"{finding.kind.value:<18} ({x0},{y0})-({x1},{y1})  "
            f"{finding.message}"
        )

    if not verbose and len(shown) < total:
        lines.append("")
        lines.append(f"({total - len(shown)} cosmetic findings hidden; use --verbose)")

    return "\n".join(lines)


def to_json(result: ComparisonResult, path: str | Path) -> Path:
    """Write the full result as JSON. Keys are sorted so output is diffable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return path


def to_annotated_pdf(result: ComparisonResult, path: str | Path) -> Path:
    """Write a copy of the new drawing with every finding boxed and labelled."""
    import fitz

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(result.new_path)
    try:
        for finding in result.sorted_findings():
            if finding.page >= doc.page_count:
                continue
            if finding.bbox.area <= 0:
                continue
            page = doc[finding.page]
            colour = _SEVERITY_COLOURS[finding.severity]
            rect = fitz.Rect(*finding.bbox.as_tuple())
            page.draw_rect(rect, color=colour, width=1.2)
            page.insert_text(
                fitz.Point(rect.x0, max(8.0, rect.y0 - 3.0)),
                finding.kind.value,
                fontsize=6,
                color=colour,
            )
        doc.save(str(path))
    finally:
        doc.close()
    return path
