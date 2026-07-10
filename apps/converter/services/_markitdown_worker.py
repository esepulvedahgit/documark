"""Standalone conversion worker, invoked as a plain ``subprocess.Popen``
child by MarkItDownService (apps/converter/services/markitdown_service.py).

Deliberately NOT a Django-aware module and NOT using ``multiprocessing`` —
this script is spawned via ``subprocess``, which has none of
``multiprocessing.Process``'s "daemonic processes are not allowed to have
children" restriction. That restriction is exactly what broke conversions
when they started running inside a Celery prefork worker (itself a daemon
process): forking a *second* level of child from there was fine with plain
subprocess, but not with multiprocessing.

Usage: python _markitdown_worker.py <input_path> <output_path>
Exit codes: 0 ok, 1 conversion error (message on stderr), 2 empty result.
"""

import sys


def main() -> int:
    input_path, output_path = sys.argv[1], sys.argv[2]

    try:
        from markitdown import MarkItDown

        result = MarkItDown().convert(input_path)
    except Exception as exc:  # MarkItDown raises a variety of internal errors
        print(str(exc), file=sys.stderr)
        return 1

    text = getattr(result, "text_content", None)
    if not text:
        return 2

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
