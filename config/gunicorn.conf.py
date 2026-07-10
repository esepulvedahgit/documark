"""Gunicorn configuration, tunable via environment variables.

Defaults are generous on purpose: MarkItDown conversion (pdfminer/pdfplumber
for PDFs especially) is a synchronous, CPU-bound call inside the request. The
30s Gunicorn default timeout is easily exceeded by a large/complex PDF, and
when it fires Gunicorn SIGABRTs the worker mid-request — an uncontrolled
crash, not the friendly "failed" conversion result the app is supposed to
produce. See apps/converter/services/markitdown_service.py for the
complementary, shorter, in-process timeout that turns runaway conversions
into a controlled failure before Gunicorn's timeout would ever need to act.
"""

import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, os.cpu_count() or 1)))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "300"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", str(timeout)))
