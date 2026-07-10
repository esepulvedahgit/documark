#!/usr/bin/env python
"""Standalone entry point to create the initial admin without going through
`manage.py`. Equivalent to `python manage.py create_initial_admin`.

Usage:
    python scripts/create_admin.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from apps.accounts.services.auth_service import ensure_initial_admin

if __name__ == "__main__":
    ensure_initial_admin()
    print("create_initial_admin: done (see logs for details).")
