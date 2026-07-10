"""Celery application for documark.

Redis is used purely as a message broker (and, separately, as the
django-ratelimit cache backend) — it holds no business data. Users and
conversion history stay in the encrypted file repositories exactly as
before; Celery/Redis only replace the hand-rolled background-thread
mechanism used to run conversions without blocking the HTTP request.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("documark")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
