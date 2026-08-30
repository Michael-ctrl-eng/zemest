"""Tests for Egyptian phone number validation and normalization."""
import pytest

from app.utils.phone import normalize_egyptian_phone, validate_egyptian_phone


class TestEgyptianPhoneValidation:
    def test_valid_vodafone(self):
        assert validate_egyptian_phone("01011234567") is True

    def test_valid_etisalat(self):
        assert validate_egyptian_phone("01111234567") is True

    def test_valid_orange(self):
        assert validate_egyptian_phone("01211234567") is True

    def test_valid_we(self):
        assert validate_egyptian_phone("01511234567") is True

    def test_valid_with_country_code(self):
        assert validate_egyptian_phone("201011234567") is True

    def test_valid_with_plus(self):
        assert validate_egyptian_phone("+201011234567") is True

    def test_valid_with_spaces(self):
        assert validate_egyptian_phone("010 1123 4567") is True

    def test_valid_with_dashes(self):
        assert validate_egyptian_phone("010-1123-4567") is True

    def test_invalid_too_short(self):
        assert validate_egyptian_phone("0101123456") is False

    def test_invalid_too_long(self):
        assert validate_egyptian_phone("010112345678") is False

    def test_invalid_prefix(self):
        assert validate_egyptian_phone("02012345678") is False

    def test_invalid_letters(self):
        assert validate_egyptian_phone("12345678901") is False

    def test_empty(self):
        assert validate_egyptian_phone("") is False


class TestEgyptianPhoneNormalization:
    def test_from_country_code(self):
        assert normalize_egyptian_phone("201011234567") == "01011234567"

    def test_from_plus_country_code(self):
        assert normalize_egyptian_phone("+201011234567") == "01011234567"

    def test_already_normalized(self):
        assert normalize_egyptian_phone("01011234567") == "01011234567"

    def test_with_spaces(self):
        assert normalize_egyptian_phone("010 1123 4567") == "01011234567"
