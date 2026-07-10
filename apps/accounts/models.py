"""Django ORM model backing DjangoUserRepository.

Field-for-field mirror of the ``User`` dataclass in
apps/accounts/repositories/base.py — kept in sync deliberately so
DjangoUserRepository's to-dataclass/from-dataclass mapping stays trivial.
"""

from django.db import models

from apps.accounts.repositories.base import ROLES


class UserProfile(models.Model):
    id = models.CharField(primary_key=True, max_length=36)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=[(r, r) for r in ROLES])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "accounts_userprofile"

    def __str__(self):
        return self.username
