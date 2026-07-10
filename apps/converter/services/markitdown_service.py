"""Thin adapter around MarkItDown — the only place in the project that
triggers a MarkItDown conversion (the library call itself lives in the
standalone ``_markitdown_worker.py`` script this spawns).

Isolating it here means an upstream MarkItDown API change (the library
releases often — see requirements-markitdown.txt and
scripts/update_markitdown.sh) only ever requires editing
``_markitdown_worker.py``. Views never call MarkItDown directly; they go
through conversion_service, which goes through this service.

The conversion runs in a ``subprocess.Popen`` child with a hard timeout
(``DOCUMARK_CONVERSION_TIMEOUT_SECONDS``). Two independent problems this
solves, both hit in production:

1. A large/complex PDF can take Gunicorn's worker timeout down with it
   (SIGABRT mid-request). Running the conversion out-of-process lets us
   enforce our own, shorter timeout and actually reclaim the CPU/memory
   (``kill()``) if a document hangs, turning it into a normal
   ConversionError instead of crashing the caller.
2. This used to shell out via ``multiprocessing.Process`` (fork), which
   works fine from a Gunicorn worker/thread but raises
   ``AssertionError: daemonic processes are not allowed to have children``
   when called from inside a Celery prefork worker (itself a daemon
   process). Plain ``subprocess.Popen`` has no such restriction and works
   identically everywhere — we don't need multiprocessing's shared-memory
   semantics anyway, since the result is already handed back via a temp
   file rather than an in-memory object.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings

_WORKER_SCRIPT = Path(__file__).with_name("_markitdown_worker.py")


class ConversionError(Exception):
    """Raised when a document can't be converted to Markdown."""


class MarkItDownService:
    def convert_to_markdown(self, input_path: Path, timeout: int = None) -> str:
        timeout = timeout or settings.DOCUMARK_CONVERSION_TIMEOUT_SECONDS

        output_file = tempfile.NamedTemporaryFile(prefix="documark-conversion-", suffix=".md", delete=False)
        output_path = Path(output_file.name)
        output_file.close()

        try:
            process = subprocess.Popen(
                [sys.executable, str(_WORKER_SCRIPT), str(input_path), str(output_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            try:
                _, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise ConversionError(
                    f"La conversión superó el tiempo máximo permitido ({timeout}s) y fue cancelada."
                )

            if process.returncode == 2:
                raise ConversionError("La conversión no produjo contenido Markdown.")
            if process.returncode != 0:
                message = stderr.decode("utf-8", errors="replace").strip()
                message = message or f"el proceso de conversión terminó con código {process.returncode}"
                raise ConversionError(f"No se pudo convertir el documento: {message}")

            text = output_path.read_text(encoding="utf-8")
            if not text:
                raise ConversionError("La conversión no produjo contenido Markdown.")
            return text
        finally:
            output_path.unlink(missing_ok=True)
