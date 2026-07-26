"""drawing-diff — compare two engineering drawing PDFs and report what changed."""

from .compare import compare_drawings
from .dimensions import Dimension, is_dimension, parse_dimension
from .models import (
    BBox,
    ComparisonResult,
    Finding,
    FindingKind,
    Severity,
    TextSpan,
)

__version__ = "0.1.0"

__all__ = [
    "compare_drawings",
    "parse_dimension",
    "is_dimension",
    "Dimension",
    "BBox",
    "ComparisonResult",
    "Finding",
    "FindingKind",
    "Severity",
    "TextSpan",
    "__version__",
]
