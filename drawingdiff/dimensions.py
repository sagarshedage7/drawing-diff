"""Parsing of engineering-dimension text.

Recognises the notation used on ISO-style mechanical drawings so that a change
from ``25.0`` to ``25.5`` can be reported as a dimension change rather than as
an anonymous blob of moved pixels.

Deliberately conventional: diameter/radius/thread prefixes, comma or dot as the
decimal separator, symmetric and asymmetric tolerances, and fits like ``H7``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Unicode symbols that appear on drawings, with the ASCII fallbacks CAD
# exporters often emit instead. The patterns below are built from these, so
# adding a notation here is enough to support it.
DIAMETER_SYMBOLS = ("Ø", "⌀", "%%c", "DIA")
DEGREE_SYMBOLS = ("°", "DEG")
PLUS_MINUS_SYMBOLS = ("±", "+/-", "+-")

_NUMBER = r"\d+(?:[.,]\d+)?"
_FIT = r"[A-Za-z]{1,2}\d{1,2}"


def _alternation(symbols: tuple[str, ...], trailing_space: bool = False) -> str:
    """Build a regex alternation from literal symbols, longest first.

    Longest-first matters so that ``+/-`` is not partially consumed by ``+-``.
    """
    escaped = sorted((re.escape(s) for s in symbols), key=len, reverse=True)
    suffix = r"\s*" if trailing_space else ""
    return "(?:" + "|".join(escaped) + ")" + suffix


_DIAMETER_ALT = _alternation(DIAMETER_SYMBOLS, trailing_space=True)
_DEGREE_ALT = _alternation(DEGREE_SYMBOLS)
_PLUS_MINUS_ALT = _alternation(PLUS_MINUS_SYMBOLS)

# Order matters: the most specific patterns are tried first.
_PATTERNS: list[tuple[str, str]] = [
    # M10x1.5 / M10 x 1,5
    ("thread", rf"^M(?P<value>{_NUMBER})(?:\s*[x×]\s*(?P<pitch>{_NUMBER}))?$"),
    # Ø25.4 H7 / Ø25,4h7
    ("diameter", rf"^{_DIAMETER_ALT}(?P<value>{_NUMBER})\s*(?P<fit>{_FIT})?$"),
    # R5 / R 5,0
    ("radius", rf"^R\s*(?P<value>{_NUMBER})$"),
    # 45° / 45 DEG
    ("angle", rf"^(?P<value>{_NUMBER})\s*{_DEGREE_ALT}$"),
    # 25.4 H7
    ("linear_fit", rf"^(?P<value>{_NUMBER})\s*(?P<fit>{_FIT})$"),
    # bare 25.4
    ("linear", rf"^(?P<value>{_NUMBER})$"),
]

# Tolerances, stripped off before the base value is matched.
_SYMMETRIC_TOL = re.compile(rf"{_PLUS_MINUS_ALT}\s*(?P<tol>{_NUMBER})")
_ASYMMETRIC_TOL = re.compile(
    rf"\+\s*(?P<upper>{_NUMBER})\s*/?\s*-\s*(?P<lower>{_NUMBER})"
)


@dataclass(frozen=True)
class Dimension:
    """A parsed dimension callout."""

    raw: str
    kind: str                     # linear | diameter | radius | angle | thread
    value: float
    fit: str | None = None        # e.g. H7
    pitch: float | None = None    # thread pitch
    tol_upper: float | None = None
    tol_lower: float | None = None

    @property
    def has_tolerance(self) -> bool:
        return self.tol_upper is not None or self.tol_lower is not None

    def value_differs_from(self, other: "Dimension", eps: float = 1e-6) -> bool:
        return abs(self.value - other.value) > eps or self.fit != other.fit

    def tolerance_differs_from(self, other: "Dimension", eps: float = 1e-6) -> bool:
        def close(a: float | None, b: float | None) -> bool:
            if a is None and b is None:
                return True
            if a is None or b is None:
                return False
            return abs(a - b) <= eps

        return not (close(self.tol_upper, other.tol_upper)
                    and close(self.tol_lower, other.tol_lower))

    def describe(self) -> str:
        parts = [self.raw.strip()]
        if self.has_tolerance:
            parts.append(f"(tol +{self.tol_upper}/-{self.tol_lower})")
        return " ".join(parts)


def _to_float(text: str) -> float:
    """Parse a number written with either a dot or a comma decimal separator."""
    return float(text.replace(",", "."))


def _normalise(text: str) -> str:
    """Collapse whitespace and unify the ASCII fallbacks to real symbols."""
    out = " ".join(text.split())
    out = out.replace("%%c", "Ø").replace("%%d", "°")
    return out.strip()


def parse_dimension(text: str) -> Dimension | None:
    """Parse a dimension callout, or return None if the text is not one.

    >>> parse_dimension("Ø25,4 H7").value
    25.4
    >>> parse_dimension("50 ±0.1").tol_upper
    0.1
    >>> parse_dimension("SECTION A-A") is None
    True
    """
    if not text:
        return None

    raw = _normalise(text)
    if not raw:
        return None

    body = raw
    tol_upper: float | None = None
    tol_lower: float | None = None

    asym = _ASYMMETRIC_TOL.search(body)
    if asym:
        tol_upper = _to_float(asym.group("upper"))
        tol_lower = _to_float(asym.group("lower"))
        body = body[: asym.start()] + body[asym.end():]
    else:
        sym = _SYMMETRIC_TOL.search(body)
        if sym:
            tol_upper = tol_lower = _to_float(sym.group("tol"))
            body = body[: sym.start()] + body[sym.end():]

    body = " ".join(body.split())
    if not body:
        return None

    for kind, pattern in _PATTERNS:
        m = re.match(pattern, body, flags=re.IGNORECASE)
        if not m:
            continue
        groups = m.groupdict()
        pitch = groups.get("pitch")
        return Dimension(
            raw=raw,
            kind="linear" if kind == "linear_fit" else kind,
            value=_to_float(groups["value"]),
            fit=(groups.get("fit") or None),
            pitch=_to_float(pitch) if pitch else None,
            tol_upper=tol_upper,
            tol_lower=tol_lower,
        )
    return None


def is_dimension(text: str) -> bool:
    """True when the text parses as a dimension callout."""
    return parse_dimension(text) is not None
