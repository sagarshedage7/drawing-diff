"""Console output must survive a legacy Windows code page.

Regression test for a crash found by CI: findings are reported as
``360 → 365``, and U+2192 has no mapping in cp1252. Windows Python writes
to the console using that code page, so the tool raised UnicodeEncodeError
on every dimension change — after the comparison had already succeeded.

These tests reproduce the condition on any platform by pointing stdout at a
genuine cp1252 stream.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drawingdiff import cli                        # noqa: E402
from tools.make_samples import make_pair           # noqa: E402


@pytest.fixture(scope="module")
def samples(tmp_path_factory) -> tuple[Path, Path]:
    return make_pair(tmp_path_factory.mktemp("encoding-samples"))


class _Cp1252Stream(io.TextIOWrapper):
    """A stdout that behaves like a stock Windows console."""

    def __init__(self):
        super().__init__(io.BytesIO(), encoding="cp1252", newline="")


def test_arrow_is_unencodable_in_cp1252():
    """Guard the premise: if this ever stops being true the test below is moot."""
    with pytest.raises(UnicodeEncodeError):
        "360 → 365".encode("cp1252")


def test_cli_survives_cp1252_stdout(samples, monkeypatch):
    """The end-to-end case CI caught: a run that reports a dimension change."""
    old, new = samples
    stream = _Cp1252Stream()
    monkeypatch.setattr(sys, "stdout", stream)

    # Must not raise. Without _configure_output_encoding this is exactly
    # where the Windows job died.
    exit_code = cli.main([str(old), str(new), "--dpi", "72"])

    stream.flush()
    assert exit_code == 0


def test_configure_output_encoding_switches_to_utf8(monkeypatch):
    stream = _Cp1252Stream()
    monkeypatch.setattr(sys, "stdout", stream)

    cli._configure_output_encoding()

    assert stream.encoding.lower().replace("-", "") == "utf8"
    stream.write("360 → 365")          # must not raise
    stream.flush()


def test_configure_output_encoding_tolerates_a_non_reconfigurable_stream(monkeypatch):
    """pytest's capture object has no reconfigure(); that must not be fatal."""

    class Captured:
        encoding = "utf-8"

        def write(self, text):
            return len(text)

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", Captured())
    cli._configure_output_encoding()   # must not raise
