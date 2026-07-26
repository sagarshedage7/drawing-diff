"""Generate synthetic drawing PDFs to test against.

Everything the comparison is exercised on is drawn here from scratch, so the
repository carries no real drawings from anywhere. Run this to produce a pair
of revisions with a known, deliberate set of differences.

    python tools/make_samples.py samples/

Produces:
    rev_a.pdf   baseline
    rev_b.pdf   a dimension change, a tolerance change, a note added,
                a note removed, and an extra hole
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz

# A4 landscape, in points.
PAGE_W, PAGE_H = 842.0, 595.0

LINE = (0.0, 0.0, 0.0)
THIN = 0.7
THICK = 1.2


def _frame(page: fitz.Page, title: str, revision: str) -> None:
    """Border and title block — the furniture every drawing has."""
    page.draw_rect(fitz.Rect(20, 20, PAGE_W - 20, PAGE_H - 20),
                   color=LINE, width=THICK)

    tb = fitz.Rect(PAGE_W - 280, PAGE_H - 110, PAGE_W - 20, PAGE_H - 20)
    page.draw_rect(tb, color=LINE, width=THICK)
    page.draw_line(fitz.Point(tb.x0, tb.y0 + 30),
                   fitz.Point(tb.x1, tb.y0 + 30), color=LINE, width=THIN)
    page.draw_line(fitz.Point(tb.x0, tb.y0 + 60),
                   fitz.Point(tb.x1, tb.y0 + 60), color=LINE, width=THIN)

    page.insert_text(fitz.Point(tb.x0 + 8, tb.y0 + 20), title, fontsize=11)
    page.insert_text(fitz.Point(tb.x0 + 8, tb.y0 + 50),
                     "MATERIAL: STEEL S235", fontsize=8)
    page.insert_text(fitz.Point(tb.x0 + 8, tb.y0 + 80),
                     f"REVISION: {revision}", fontsize=8)
    page.insert_text(fitz.Point(tb.x0 + 150, tb.y0 + 80),
                     "SCALE 1:2", fontsize=8)


def _plate(page: fitz.Page, extra_hole: bool) -> None:
    """A rectangular plate with holes — the 'part' being drawn."""
    outline = fitz.Rect(120, 140, 480, 380)
    page.draw_rect(outline, color=LINE, width=THICK)

    # Corner holes.
    for cx, cy in ((160, 180), (440, 180), (160, 340), (440, 340)):
        page.draw_circle(fitz.Point(cx, cy), 12, color=LINE, width=THIN)
        page.draw_line(fitz.Point(cx - 18, cy), fitz.Point(cx + 18, cy),
                       color=LINE, width=0.4)
        page.draw_line(fitz.Point(cx, cy - 18), fitz.Point(cx, cy + 18),
                       color=LINE, width=0.4)

    # Central bore.
    page.draw_circle(fitz.Point(300, 260), 45, color=LINE, width=THICK)

    if extra_hole:
        # The added feature in revision B.
        page.draw_circle(fitz.Point(300, 180), 10, color=LINE, width=THIN)
        page.draw_line(fitz.Point(282, 180), fitz.Point(318, 180),
                       color=LINE, width=0.4)
        page.draw_line(fitz.Point(300, 162), fitz.Point(300, 198),
                       color=LINE, width=0.4)

    # Dimension witness lines.
    page.draw_line(fitz.Point(120, 410), fitz.Point(480, 410),
                   color=LINE, width=THIN)
    page.draw_line(fitz.Point(80, 140), fitz.Point(80, 380),
                   color=LINE, width=THIN)


def _build(path: Path, *, width_dim: str, bore_dim: str, thickness: str,
           revision: str, extra_hole: bool, notes: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W, height=PAGE_H)

    _frame(page, "MOUNTING PLATE", revision)
    _plate(page, extra_hole)

    # Dimension callouts — positions stay fixed between revisions so the
    # positional matcher pairs them up.
    page.insert_text(fitz.Point(285, 425), width_dim, fontsize=10)
    page.insert_text(fitz.Point(40, 265), thickness, fontsize=10)
    page.insert_text(fitz.Point(310, 258), bore_dim, fontsize=10)
    page.insert_text(fitz.Point(150, 210), "4x Ø12", fontsize=9)

    page.insert_text(fitz.Point(60, 80), "GENERAL NOTES:", fontsize=9)
    for i, note in enumerate(notes):
        page.insert_text(fitz.Point(60, 96 + i * 14), note, fontsize=8)

    doc.save(str(path))
    doc.close()


def make_pair(out_dir: Path) -> tuple[Path, Path]:
    """Write rev_a.pdf and rev_b.pdf, and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rev_a = out_dir / "rev_a.pdf"
    rev_b = out_dir / "rev_b.pdf"

    _build(
        rev_a,
        width_dim="360",
        bore_dim="Ø90 ±0.1",
        thickness="12",
        revision="A",
        extra_hole=False,
        notes=[
            "1. DEBURR ALL SHARP EDGES",
            "2. SURFACE FINISH Ra 3,2",
            "3. TOLERANCES PER ISO 2768-m",
        ],
    )

    _build(
        rev_b,
        width_dim="365",              # dimension changed 360 -> 365
        bore_dim="Ø90 ±0.05",         # tolerance tightened
        thickness="12",
        revision="B",
        extra_hole=True,              # geometry added
        notes=[
            "1. DEBURR ALL SHARP EDGES",
            "2. SURFACE FINISH Ra 3,2",
            "4. ZINC PLATE PER ISO 4042",   # note 3 removed, note 4 added
        ],
    )
    return rev_a, rev_b


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "out_dir", nargs="?", type=Path, default=Path("samples"),
        help="where to write the PDFs (default: ./samples)",
    )
    args = parser.parse_args()
    a, b = make_pair(args.out_dir)
    print(f"wrote {a}")
    print(f"wrote {b}")
    print("\nExpected differences:")
    print("  - width dimension 360 -> 365      (Critical)")
    print("  - bore tolerance ±0.1 -> ±0.05    (Critical)")
    print("  - note 3 removed, note 4 added    (Major)")
    print("  - extra Ø20 hole added            (Minor)")
    print("  - revision letter A -> B          (Major)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
