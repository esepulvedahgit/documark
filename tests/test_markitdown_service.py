"""Verifies MarkItDownService's subprocess isolation and timeout handling.

Two real production bugs this guards against:
1. A slow/adversarial conversion running past Gunicorn's worker timeout used
   to take the whole worker down (SIGABRT) instead of failing cleanly.
2. The original fix used ``multiprocessing.Process`` (fork), which raises
   ``AssertionError: daemonic processes are not allowed to have children``
   when called from inside a Celery prefork worker. Switching to plain
   ``subprocess.Popen`` (see markitdown_service.py) has no such restriction.

Because the conversion now runs in a genuinely separate ``subprocess.Popen``
process (not a fork), monkeypatching ``markitdown.MarkItDown`` in the test
process has no effect on the child — these tests exercise the real
MarkItDown library on small real files instead.
"""

import time

import pytest

from apps.converter.services.markitdown_service import ConversionError, MarkItDownService


def test_convert_to_markdown_success(tmp_path):
    input_path = tmp_path / "doc.txt"
    input_path.write_text("hola mundo, contenido de prueba", encoding="utf-8")

    text = MarkItDownService().convert_to_markdown(input_path, timeout=30)
    assert "hola mundo, contenido de prueba" in text


def test_convert_to_markdown_wraps_library_errors(tmp_path):
    missing_path = tmp_path / "no_existe.txt"  # never written — real MarkItDown error

    with pytest.raises(ConversionError, match="No se pudo convertir"):
        MarkItDownService().convert_to_markdown(missing_path, timeout=30)


def test_convert_to_markdown_cancels_after_timeout(tmp_path):
    input_path = tmp_path / "doc.txt"
    input_path.write_text("hola mundo", encoding="utf-8")

    started = time.monotonic()
    with pytest.raises(ConversionError, match="tiempo máximo"):
        # A real conversion can't start (interpreter spawn + imports) in
        # 10ms, so this reliably exercises the kill-on-timeout path without
        # needing a slow/huge fixture file.
        MarkItDownService().convert_to_markdown(input_path, timeout=0.01)
    elapsed = time.monotonic() - started

    # Must return shortly after the timeout, not after a real conversion
    # would've finished — proves the subprocess was actually killed.
    assert elapsed < 5
