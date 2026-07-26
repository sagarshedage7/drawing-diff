"""Core data types shared across the comparison pipeline.

Everything here is a plain frozen dataclass so that findings are hashable,
sortable, and trivially serialisable to JSON.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from typing import Any


class Severity(enum.IntEnum):
    """How much a reviewer should care. Ordered so sorting puts the worst first."""

    CRITICAL = 0      # a dimension or tolerance value changed
    MAJOR = 1         # text added or removed
    MINOR = 2         # geometry changed in a localised region
    COSMETIC = 3      # small pixel-level differences, likely rendering noise

    @property
    def label(self) -> str:
        return self.name.capitalize()


class FindingKind(str, enum.Enum):
    DIMENSION_CHANGED = "DimensionChanged"
    TOLERANCE_CHANGED = "ToleranceChanged"
    TEXT_ADDED = "TextAdded"
    TEXT_REMOVED = "TextRemoved"
    TEXT_CHANGED = "TextChanged"
    GEOMETRY_CHANGED = "GeometryChanged"
    PAGE_COUNT_CHANGED = "PageCountChanged"
    PAGE_SIZE_CHANGED = "PageSizeChanged"


@dataclass(frozen=True, order=True)
class BBox:
    """Axis-aligned box in PDF points, origin top-left."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def rounded(self, ndigits: int = 2) -> "BBox":
        return BBox(
            round(self.x0, ndigits), round(self.y0, ndigits),
            round(self.x1, ndigits), round(self.y1, ndigits),
        )

    def union(self, other: "BBox") -> "BBox":
        return BBox(
            min(self.x0, other.x0), min(self.y0, other.y0),
            max(self.x1, other.x1), max(self.y1, other.y1),
        )

    def intersects(self, other: "BBox", pad: float = 0.0) -> bool:
        return not (
            self.x1 + pad < other.x0
            or other.x1 + pad < self.x0
            or self.y1 + pad < other.y0
            or other.y1 + pad < self.y0
        )

    def distance_to(self, other: "BBox") -> float:
        """Euclidean distance between box centres."""
        ax, ay = self.centre
        bx, by = other.centre
        return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True)
class TextSpan:
    """A run of text on a page, with where it sits."""

    text: str
    bbox: BBox
    page: int
    size: float = 0.0

    @property
    def normalised(self) -> str:
        """Whitespace-collapsed text, for comparison purposes."""
        return " ".join(self.text.split())


@dataclass(frozen=True, order=True)
class Finding:
    """One reported difference between two drawings.

    Ordering is (severity, page, kind, bbox) so a sorted list of findings is
    stable across runs — a hard requirement for the determinism tests.
    """

    severity: Severity
    page: int
    kind: FindingKind
    bbox: BBox
    message: str = field(compare=False)
    old_value: str | None = field(default=None, compare=False)
    new_value: str | None = field(default=None, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.label,
            "page": self.page,
            "kind": self.kind.value,
            "bbox": [round(v, 2) for v in self.bbox.as_tuple()],
            "message": self.message,
            "old_value": self.old_value,
            "new_value": self.new_value,
        }


@dataclass
class ComparisonResult:
    """Everything one comparison produced."""

    old_path: str
    new_path: str
    findings: list[Finding] = field(default_factory=list)
    pages_compared: int = 0
    dpi: int = 200

    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings)

    def counts_by_severity(self) -> dict[str, int]:
        counts = {s.label: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.label] += 1
        return counts

    @property
    def has_blocking_findings(self) -> bool:
        return any(f.severity <= Severity.MAJOR for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "old": self.old_path,
            "new": self.new_path,
            "pages_compared": self.pages_compared,
            "dpi": self.dpi,
            "counts": self.counts_by_severity(),
            "findings": [f.to_dict() for f in self.sorted_findings()],
        }
