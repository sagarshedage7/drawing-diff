"""Reading text and page images out of a PDF drawing.

Thin wrapper over PyMuPDF so the rest of the package never imports fitz
directly and can be unit-tested against plain dataclasses.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from .models import BBox, TextSpan


class DrawingDocument:
    """An opened PDF drawing."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"No such PDF: {self.path}")
        self._doc = fitz.open(str(self.path))

    def __enter__(self) -> "DrawingDocument":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._doc.close()

    @property
    def page_count(self) -> int:
        return self._doc.page_count

    def page_size(self, page: int) -> tuple[float, float]:
        rect = self._doc[page].rect
        return (round(rect.width, 2), round(rect.height, 2))

    def text_spans(self, page: int) -> list[TextSpan]:
        """Every non-empty text span on a page, in deterministic order.

        Spans are sorted top-to-bottom then left-to-right so that two runs over
        the same file always produce an identical list.
        """
        spans: list[TextSpan] = []
        raw = self._doc[page].get_text("dict")
        for block in raw.get("blocks", []):
            if block.get("type") != 0:      # 0 = text block, 1 = image
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append(
                        TextSpan(
                            text=text,
                            bbox=BBox(x0, y0, x1, y1).rounded(),
                            page=page,
                            size=round(span.get("size", 0.0), 2),
                        )
                    )
        spans.sort(key=lambda s: (round(s.bbox.y0, 1), round(s.bbox.x0, 1), s.text))
        return spans

    def has_text_layer(self, page: int) -> bool:
        """False for scanned drawings, which need a different strategy."""
        return bool(self.text_spans(page))

    def render(self, page: int, dpi: int = 200):
        """Render a page to a greyscale numpy array.

        Imported lazily so that text-only use of the package does not require
        numpy to be installed.
        """
        import numpy as np

        zoom = dpi / 72.0
        pix = self._doc[page].get_pixmap(
            matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY, alpha=False
        )
        buf = np.frombuffer(pix.samples, dtype=np.uint8)
        return buf.reshape(pix.height, pix.width).copy()
