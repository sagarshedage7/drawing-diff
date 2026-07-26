"""Top-level comparison: run every stage over a pair of PDFs."""

from __future__ import annotations

from pathlib import Path

from .extract import DrawingDocument
from .models import (
    BBox,
    ComparisonResult,
    Finding,
    FindingKind,
    Severity,
)
from .rasterdiff import compare_raster
from .textdiff import compare_text


def compare_drawings(
    old_path: str | Path,
    new_path: str | Path,
    dpi: int = 200,
    ignore: list[BBox] | None = None,
    skip_raster: bool = False,
) -> ComparisonResult:
    """Compare two drawing PDFs and return every difference found.

    The result is deterministic: the same two files always produce the same
    findings in the same order.
    """
    result = ComparisonResult(
        old_path=str(old_path), new_path=str(new_path), dpi=dpi
    )

    with DrawingDocument(old_path) as old_doc, DrawingDocument(new_path) as new_doc:
        if old_doc.page_count != new_doc.page_count:
            result.findings.append(
                Finding(
                    severity=Severity.MAJOR,
                    page=0,
                    kind=FindingKind.PAGE_COUNT_CHANGED,
                    bbox=BBox(0, 0, 0, 0),
                    message=(
                        f"Page count changed: {old_doc.page_count} → "
                        f"{new_doc.page_count}"
                    ),
                    old_value=str(old_doc.page_count),
                    new_value=str(new_doc.page_count),
                )
            )

        pages = min(old_doc.page_count, new_doc.page_count)
        result.pages_compared = pages

        for page in range(pages):
            old_size = old_doc.page_size(page)
            new_size = new_doc.page_size(page)
            if old_size != new_size:
                result.findings.append(
                    Finding(
                        severity=Severity.MINOR,
                        page=page,
                        kind=FindingKind.PAGE_SIZE_CHANGED,
                        bbox=BBox(0, 0, 0, 0),
                        message=f"Sheet size changed: {old_size} → {new_size} pt",
                        old_value=str(old_size),
                        new_value=str(new_size),
                    )
                )

            result.findings.extend(
                compare_text(
                    old_doc.text_spans(page), new_doc.text_spans(page), page
                )
            )

            if not skip_raster:
                result.findings.extend(
                    compare_raster(
                        old_doc.render(page, dpi),
                        new_doc.render(page, dpi),
                        page=page,
                        dpi=dpi,
                        ignore=ignore,
                    )
                )

    result.findings = result.sorted_findings()
    return result
