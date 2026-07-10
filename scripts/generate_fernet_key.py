#!/usr/bin/env python
"""Generates a Fernet key for DOCUMARK_FERNET_KEY.

Usage:
    python scripts/generate_fernet_key.py

Copy the printed value into your .env as DOCUMARK_FERNET_KEY=<value>.
Never commit this key. Losing it makes all encrypted data unreadable;
rotating it requires re-encrypting storage/secure/*.enc (see README).
"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print(Fernet.generate_key().decode())
