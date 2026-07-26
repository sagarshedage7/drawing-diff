"""Pixel-level comparison of two rendered drawing pages.

Catches everything the text layer cannot: added or deleted geometry, moved
views, changed hatching. The output is a small number of clustered regions
rather than a raw difference image, so a reviewer gets "here are six places to
look" instead of a wall of noise.
"""

from __future__ import annotations

import numpy as np

from .models import BBox, Finding, FindingKind, Severity

# A pixel counts as different when the two greyscale values differ by more than
# this. Anti-aliasing along an unchanged line typically lands well under it.
INTENSITY_THRESHOLD = 40

# Regions smaller than this (in rendered pixels) are dropped as noise.
MIN_REGION_AREA = 60

# Differing pixels closer than this are treated as one region.
CLUSTER_GAP = 12


def _to_common_shape(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crop both images to their overlapping extent.

    Pages of slightly different size still compare usefully; the size change
    itself is reported separately as its own finding.
    """
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    return a[:h, :w], b[:h, :w]


def _cluster(mask: np.ndarray, gap: int) -> list[tuple[int, int, int, int]]:
    """Group set pixels into rectangles using a coarse grid.

    A full connected-component labelling would be more precise, but a grid of
    ``gap``-sized cells is O(n) with no SciPy dependency and produces the same
    review regions in practice, because what matters is "roughly where", not
    exact pixel membership.
    """
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return []

    # Bucket each differing pixel into a coarse cell, then merge adjacent cells.
    cells: dict[tuple[int, int], list[int]] = {}
    for y, x in zip(ys.tolist(), xs.tolist()):
        key = (y // gap, x // gap)
        box = cells.get(key)
        if box is None:
            cells[key] = [x, y, x, y]
        else:
            if x < box[0]:
                box[0] = x
            if y < box[1]:
                box[1] = y
            if x > box[2]:
                box[2] = x
            if y > box[3]:
                box[3] = y

    # Union-find over 8-connected cells.
    parent: dict[tuple[int, int], tuple[int, int]] = {k: k for k in cells}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for (cy, cx) in cells:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                neighbour = (cy + dy, cx + dx)
                if neighbour in cells:
                    union((cy, cx), neighbour)

    merged: dict[tuple[int, int], list[int]] = {}
    for key, box in cells.items():
        root = find(key)
        cur = merged.get(root)
        if cur is None:
            merged[root] = list(box)
        else:
            cur[0] = min(cur[0], box[0])
            cur[1] = min(cur[1], box[1])
            cur[2] = max(cur[2], box[2])
            cur[3] = max(cur[3], box[3])

    regions = [tuple(v) for v in merged.values()]
    regions.sort()
    return regions


def compare_raster(
    old_image: np.ndarray,
    new_image: np.ndarray,
    page: int,
    dpi: int,
    intensity_threshold: int = INTENSITY_THRESHOLD,
    min_area: int = MIN_REGION_AREA,
    cluster_gap: int = CLUSTER_GAP,
    ignore: list[BBox] | None = None,
) -> list[Finding]:
    """Diff two rendered pages into clustered geometry findings.

    ``ignore`` takes boxes in PDF points (e.g. the title block, which changes
    on every revision and would otherwise dominate the report).
    """
    a, b = _to_common_shape(old_image, new_image)
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    mask = delta > intensity_threshold

    scale = dpi / 72.0
    for box in ignore or []:
        x0 = max(0, int(box.x0 * scale))
        y0 = max(0, int(box.y0 * scale))
        x1 = min(mask.shape[1], int(box.x1 * scale))
        y1 = min(mask.shape[0], int(box.y1 * scale))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = False

    findings: list[Finding] = []
    for x0, y0, x1, y1 in _cluster(mask, cluster_gap):
        area = (x1 - x0 + 1) * (y1 - y0 + 1)
        if area < min_area:
            continue
        changed = int(mask[y0:y1 + 1, x0:x1 + 1].sum())
        bbox = BBox(x0 / scale, y0 / scale, x1 / scale, y1 / scale).rounded()
        severity = Severity.MINOR if changed >= min_area else Severity.COSMETIC
        findings.append(
            Finding(
                severity=severity,
                page=page,
                kind=FindingKind.GEOMETRY_CHANGED,
                bbox=bbox,
                message=(
                    f"Geometry differs over ~{changed} px in a "
                    f"{bbox.width:.0f}×{bbox.height:.0f} pt region"
                ),
            )
        )
    return findings


def difference_ratio(old_image: np.ndarray, new_image: np.ndarray,
                     intensity_threshold: int = INTENSITY_THRESHOLD) -> float:
    """Fraction of overlapping pixels that differ. Handy as a quick summary."""
    a, b = _to_common_shape(old_image, new_image)
    if a.size == 0:
        return 0.0
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float((delta > intensity_threshold).sum()) / float(a.size)
