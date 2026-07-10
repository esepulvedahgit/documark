"""Django ORM model backing DjangoHistoryRepository.

Field-for-field mirror of the ``HistoryEntry`` dataclass in
apps/converter/repositories/base.py — kept in sync deliberately so
DjangoHistoryRepository's to-dataclass/from-dataclass mapping stays trivial.
"""

from django.db import models

from apps.converter.repositories.base import STATUSES


class ConversionHistory(models.Model):
    id = models.CharField(primary_key=True, max_length=36)
    user_id = models.CharField(max_length=36, db_index=True)
    username = models.CharField(max_length=150)
    original_filename = models.CharField(max_length=255)
    safe_filename = models.CharField(max_length=255, null=True, blank=True)
    output_filename = models.CharField(max_length=255, null=True, blank=True)
    file_extension = models.CharField(max_length=20)
    file_size = models.IntegerField()
    status = models.CharField(max_length=20, choices=[(s, s) for s in STATUSES], db_index=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "converter_conversionhistory"

    def __str__(self):
        return f"{self.original_filename} ({self.status})"
