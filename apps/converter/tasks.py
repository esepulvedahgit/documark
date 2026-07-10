"""Celery tasks — thin wrappers around the actual service logic so the
services stay testable/callable without Celery machinery.
"""

from celery import shared_task


@shared_task(bind=True, acks_late=True)
def convert_document_task(self, entry_id, upload_path_str, username):
    from apps.converter.services.conversion_service import finalize_conversion

    finalize_conversion(entry_id, upload_path_str, username)


@shared_task
def cleanup_expired_task():
    from apps.converter.services.cleanup_service import cleanup_all

    return cleanup_all()
