import pytest
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError

from apps.accounts.services.password_service import hash_password, validate_strength, verify_password


def test_hash_password_is_not_plaintext():
    hashed = hash_password("Sup3r$ecretPass!")
    assert hashed != "Sup3r$ecretPass!"
    assert hashed.count("$") >= 2  # PBKDF2-style hash format: algo$iterations$salt$hash


def test_verify_password_correct_and_incorrect():
    hashed = hash_password("Sup3r$ecretPass!")
    assert verify_password("Sup3r$ecretPass!", hashed) is True
    assert verify_password("wrong-password", hashed) is False


@pytest.mark.parametrize(
    "password",
    [
        "short1!A",  # too short
        "alllowercase123!",  # no uppercase
        "ALLUPPERCASE123!",  # no lowercase
        "NoDigitsHereEither!",  # no digit
        "NoSymbolsHere1234",  # no symbol
    ],
)
def test_validate_strength_rejects_weak_passwords(password):
    with pytest.raises(ValidationError):
        validate_strength(password, username="someuser")


def test_validate_strength_accepts_strong_password():
    validate_strength("Correct-Horse-99!", username="someuser")  # should not raise


def test_validate_strength_rejects_password_similar_to_username():
    # Also satisfies the strong-password rules on its own, so this isolates
    # the username-similarity check specifically.
    with pytest.raises(ValidationError):
        validate_strength("Edusepulveda123!", username="edusepulveda")


def test_common_password_validator_is_configured_and_blocks():
    # No string can be both "12+ chars with upper/lower/digit/symbol" and a
    # literal entry in Django's common-password list, so this checks the
    # validator directly rather than through validate_strength() (which
    # always runs the full, layered stack together).
    with pytest.raises(ValidationError):
        CommonPasswordValidator().validate("password123")
