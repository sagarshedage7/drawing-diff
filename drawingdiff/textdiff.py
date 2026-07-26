"""Comparing the text layers of two drawings.

Spans are matched by position first, then by content, because on a revised
drawing the same callout usually stays within a few points of where it was.
Anything left unmatched is reported as added or removed.
"""

from __future__ import annotations

from .dimensions import parse_dimension
from .models import BBox, Finding, FindingKind, Severity, TextSpan

# How far a span may move and still be considered "the same" callout, in points.
POSITION_TOLERANCE = 4.0


def _pair_by_position(
    old_spans: list[TextSpan],
    new_spans: list[TextSpan],
    tolerance: float,
) -> tuple[list[tuple[TextSpan, TextSpan]], list[TextSpan], list[TextSpan]]:
    """Greedily pair spans that sit in nearly the same place.

    Pairing is greedy over a deterministic ordering rather than optimal: an
    exact assignment is quadratic and, on real drawings, buys nothing because
    callouts rarely move far enough to be ambiguous.
    """
    unmatched_new = list(new_spans)
    pairs: list[tuple[TextSpan, TextSpan]] = []
    unmatched_old: list[TextSpan] = []

    for old in old_spans:
        best: TextSpan | None = None
        best_distance = tolerance
        for cand in unmatched_new:
            distance = old.bbox.distance_to(cand.bbox)
            if distance > best_distance:
                continue
            # Prefer an identical string when two candidates are equally close.
            if (best is None
                    or distance < best_distance
                    or (cand.normalised == old.normalised
                        and best.normalised != old.normalised)):
                best, best_distance = cand, distance
        if best is None:
            unmatched_old.append(old)
        else:
            pairs.append((old, best))
            unmatched_new.remove(best)

    return pairs, unmatched_old, unmatched_new


def _pair_leftovers_by_content(
    unmatched_old: list[TextSpan],
    unmatched_new: list[TextSpan],
) -> tuple[list[tuple[TextSpan, TextSpan]], list[TextSpan], list[TextSpan]]:
    """Second pass: match identical strings that simply moved."""
    pairs: list[tuple[TextSpan, TextSpan]] = []
    remaining_new = list(unmatched_new)
    remaining_old: list[TextSpan] = []

    by_text: dict[str, list[TextSpan]] = {}
    for span in remaining_new:
        by_text.setdefault(span.normalised, []).append(span)

    for old in unmatched_old:
        bucket = by_text.get(old.normalised)
        if bucket:
            partner = bucket.pop(0)
            remaining_new.remove(partner)
            pairs.append((old, partner))
        else:
            remaining_old.append(old)

    return pairs, remaining_old, remaining_new


def compare_text(
    old_spans: list[TextSpan],
    new_spans: list[TextSpan],
    page: int,
    tolerance: float = POSITION_TOLERANCE,
) -> list[Finding]:
    """Diff two pages' text layers into findings."""
    findings: list[Finding] = []

    positional, leftover_old, leftover_new = _pair_by_position(
        old_spans, new_spans, tolerance
    )
    moved, removed, added = _pair_leftovers_by_content(leftover_old, leftover_new)

    for old, new in positional:
        if old.normalised == new.normalised:
            continue
        findings.extend(_classify_change(old, new, page))

    # A span that kept its text but changed place is not interesting on its own;
    # the raster pass will flag it if the geometry around it actually moved.
    del moved

    for span in removed:
        findings.append(
            Finding(
                severity=Severity.MAJOR,
                page=page,
                kind=FindingKind.TEXT_REMOVED,
                bbox=span.bbox,
                message=f"Text removed: {span.normalised!r}",
                old_value=span.normalised,
                new_value=None,
            )
        )

    for span in added:
        findings.append(
            Finding(
                severity=Severity.MAJOR,
                page=page,
                kind=FindingKind.TEXT_ADDED,
                bbox=span.bbox,
                message=f"Text added: {span.normalised!r}",
                old_value=None,
                new_value=span.normalised,
            )
        )

    return findings


def _classify_change(old: TextSpan, new: TextSpan, page: int) -> list[Finding]:
    """Decide whether a changed span is a dimension, a tolerance, or prose."""
    bbox: BBox = old.bbox.union(new.bbox)
    old_dim = parse_dimension(old.normalised)
    new_dim = parse_dimension(new.normalised)

    if old_dim and new_dim:
        out: list[Finding] = []
        if old_dim.value_differs_from(new_dim):
            out.append(
                Finding(
                    severity=Severity.CRITICAL,
                    page=page,
                    kind=FindingKind.DIMENSION_CHANGED,
                    bbox=bbox,
                    message=(
                        f"Dimension changed: {old_dim.describe()} → "
                        f"{new_dim.describe()}"
                    ),
                    old_value=old.normalised,
                    new_value=new.normalised,
                )
            )
        if old_dim.tolerance_differs_from(new_dim):
            out.append(
                Finding(
                    severity=Severity.CRITICAL,
                    page=page,
                    kind=FindingKind.TOLERANCE_CHANGED,
                    bbox=bbox,
                    message=(
                        f"Tolerance changed: {old.normalised!r} → "
                        f"{new.normalised!r}"
                    ),
                    old_value=old.normalised,
                    new_value=new.normalised,
                )
            )
        if out:
            return out

    return [
        Finding(
            severity=Severity.MAJOR,
            page=page,
            kind=FindingKind.TEXT_CHANGED,
            bbox=bbox,
            message=f"Text changed: {old.normalised!r} → {new.normalised!r}",
            old_value=old.normalised,
            new_value=new.normalised,
        )
    ]
