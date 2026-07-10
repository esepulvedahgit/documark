import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def celery_eager(settings):
    """Runs Celery tasks synchronously, in-process, via .delay() — no real
    Redis broker needed for tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def isolated_storage(tmp_path, settings):
    """Redirects all storage/* paths to a fresh temp dir for the test's
    duration, so repository/service tests never touch the real
    storage/secure/*.enc files."""
    settings.STORAGE_ROOT = tmp_path
    from apps.core import storage

    storage.ensure_storage_dirs()
    return tmp_path
