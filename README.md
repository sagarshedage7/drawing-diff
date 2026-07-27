# drawing-diff

[![CI](https://github.com/sagarshedage7/drawing-diff/actions/workflows/ci.yml/badge.svg)](https://github.com/sagarshedage7/drawing-diff/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Compare two revisions of an engineering drawing PDF and get a reviewer-ready list of **what actually changed** — dimension values, tolerances, notes, and geometry — instead of squinting at two sheets side by side.

```console
$ drawing-diff rev_a.pdf rev_b.pdf --annotated review.pdf

Old : rev_a.pdf
New : rev_b.pdf
Pages compared: 1   DPI: 200

Findings: 7
  Critical      2
  Major         3
  Minor         2

[Critical ] p1 DimensionChanged  (285,415)-(325,435)  Dimension changed: 360 → 365
[Critical ] p1 ToleranceChanged  (310,248)-(365,268)  Tolerance changed: 'Ø90 ±0.1' → 'Ø90 ±0.05'
[Major    ] p1 TextRemoved       (60,116)-(190,128)   Text removed: '3. TOLERANCES PER ISO 2768-m'
[Major    ] p1 TextAdded         (60,116)-(185,128)   Text added: '4. ZINC PLATE PER ISO 4042'
[Major    ] p1 TextChanged       (622,540)-(700,552)  Text changed: 'REVISION: A' → 'REVISION: B'
[Minor    ] p1 GeometryChanged   (288,168)-(313,193)  Geometry differs over ~412 px in a 25×25 pt region
[Minor    ] p1 GeometryChanged   (118,405)-(482,415)  Geometry differs over ~980 px in a 364×10 pt region
```

Fully offline and deterministic — the same two files always produce the same findings in the same order.

---

## How it works

Three passes, each catching what the others cannot:

**1. Text layer.** Spans are pulled from both PDFs with their positions, then matched — first by position (a revised callout usually stays within a few points of where it was), then by content for anything left over. Unmatched spans become *added* / *removed*.

**2. Dimension parsing.** A changed span is not just "text changed". `Ø90 ±0.1` → `Ø90 ±0.05` is parsed into a structured dimension so it can be reported as a **tolerance** change specifically, at Critical severity. The parser handles diameter, radius, angle and thread callouts, comma or dot decimals, symmetric and asymmetric tolerances, ISO fits like `H7`, and the ASCII fallbacks (`%%c`, `+/-`) that CAD exporters emit instead of the real glyphs.

**3. Raster.** Both pages are rendered to greyscale and differenced pixel-wise. Differing pixels are clustered into a handful of review regions via a coarse grid and union-find, so the output is "six places to look", not a noise image. This is what catches added geometry, moved views, and changed hatching — none of which touch the text layer.

Findings are sorted worst-first and are stable across runs, which makes the JSON output diffable and the tool usable in CI.

### Severity

| Level | Meaning |
| --- | --- |
| **Critical** | A dimension value or tolerance changed |
| **Major** | Text was added, removed, or rewritten |
| **Minor** | Geometry changed in a localised region |
| **Cosmetic** | Tiny pixel differences, most likely rendering noise |

## Install

```bash
git clone https://github.com/sagarshedage7/drawing-diff.git
cd drawing-diff
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Requires Python 3.10+, [PyMuPDF](https://pymupdf.readthedocs.io), and NumPy.

## Usage

```bash
# console summary
drawing-diff old.pdf new.pdf

# machine-readable, plus a marked-up copy of the new drawing
drawing-diff old.pdf new.pdf --json result.json --annotated review.pdf

# skip the title block, which changes on every revision
drawing-diff old.pdf new.pdf --ignore 560,480,825,580

# text only — much faster, misses geometry changes
drawing-diff old.pdf new.pdf --no-raster

# use in CI: exit 1 if anything Critical is found
drawing-diff old.pdf new.pdf --fail-on critical
```

| Option | Default | Purpose |
| --- | --- | --- |
| `--dpi N` | `200` | Render resolution for the raster pass |
| `--ignore X0,Y0,X1,Y1` | – | Mask a region, in PDF points; repeatable |
| `--no-raster` | off | Text comparison only |
| `--json PATH` | – | Write the full result as JSON |
| `--annotated PATH` | – | Copy of the new drawing with findings boxed |
| `--verbose` | off | Include cosmetic findings |
| `--fail-on LEVEL` | `never` | Exit non-zero at `any` / `major` / `critical` |

### As a library

```python
from drawingdiff import compare_drawings
from drawingdiff.models import Severity

result = compare_drawings("rev_a.pdf", "rev_b.pdf", dpi=200)

for finding in result.sorted_findings():
    if finding.severity <= Severity.MAJOR:
        print(finding.kind.value, finding.message)

print(result.counts_by_severity())   # {'Critical': 2, 'Major': 3, ...}
```

## Sample drawings

The repository ships no real drawings. The test fixtures are generated from scratch:

```bash
python tools/make_samples.py samples/
```

This writes `rev_a.pdf` and `rev_b.pdf` — a mounting plate with a deliberate set of differences (a dimension change, a tightened tolerance, one note swapped for another, and an added hole) that the test suite asserts against.

## Tests

```bash
pip install pytest
pytest
```

The suite covers dimension-notation parsing, the text matcher, and an end-to-end run over the generated samples. The most important case is `test_self_comparison_finds_nothing` — comparing a drawing against itself must produce zero findings. A comparison tool that cries wolf on an unchanged sheet is worse than no tool, so false positives are treated as failures.

## Limitations

- **Scanned drawings are out of scope.** With no text layer, only the raster pass contributes, so you get regions rather than parsed dimension changes. OCR would be the natural next step.
- Large-scale reflow (a view moved across the sheet) shows up as a big geometry region rather than "this view moved".
- The grid-based clustering is approximate by design; it favours a short review list over exact pixel membership.
- GD&T feature control frames are not parsed structurally — they compare as text.

## Roadmap

- [ ] OCR fallback for scanned sheets
- [ ] Structural parsing of GD&T frames
- [ ] Automatic title-block detection, so `--ignore` is not needed by hand
- [ ] Side-by-side HTML report

## License

MIT — see [LICENSE](LICENSE).
