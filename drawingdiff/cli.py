"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compare import compare_drawings
from .models import BBox, Severity
from .report import to_annotated_pdf, to_json, to_text


def _parse_ignore(value: str) -> BBox:
    """Parse an --ignore box given as x0,y0,x1,y1 in PDF points."""
    try:
        x0, y0, x1, y1 = (float(v) for v in value.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--ignore expects x0,y0,x1,y1 in points, got {value!r}"
        )
    return BBox(x0, y0, x1, y1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drawing-diff",
        description="Compare two engineering drawing PDFs and report what changed.",
    )
    parser.add_argument("old", type=Path, help="the earlier revision")
    parser.add_argument("new", type=Path, help="the later revision")
    parser.add_argument(
        "--dpi", type=int, default=200,
        help="render resolution for the pixel comparison (default: 200)",
    )
    parser.add_argument(
        "--ignore", type=_parse_ignore, action="append", metavar="X0,Y0,X1,Y1",
        help="ignore a region, in PDF points; repeatable "
             "(useful for the title block)",
    )
    parser.add_argument(
        "--no-raster", action="store_true",
        help="compare text only; much faster, misses geometry changes",
    )
    parser.add_argument("--json", type=Path, help="write the full result as JSON")
    parser.add_argument(
        "--annotated", type=Path,
        help="write a copy of the new drawing with findings boxed",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="include cosmetic findings in the console output",
    )
    parser.add_argument(
        "--fail-on", choices=["never", "any", "major", "critical"],
        default="never",
        help="exit non-zero when findings at this level or worse exist "
             "(default: never)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        result = compare_drawings(
            args.old, args.new,
            dpi=args.dpi,
            ignore=args.ignore,
            skip_raster=args.no_raster,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(to_text(result, verbose=args.verbose))

    if args.json:
        print(f"\nJSON written to {to_json(result, args.json)}")
    if args.annotated:
        print(f"Annotated PDF written to {to_annotated_pdf(result, args.annotated)}")

    thresholds = {
        "any": Severity.COSMETIC,
        "major": Severity.MAJOR,
        "critical": Severity.CRITICAL,
    }
    if args.fail_on != "never":
        limit = thresholds[args.fail_on]
        if any(f.severity <= limit for f in result.findings):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
