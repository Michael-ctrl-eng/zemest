"""Tests for Egyptian address validation."""
import pytest

from app.utils.egypt_address import (
    get_governorates,
    get_cities,
    get_areas_for_governorate,
    validate_egyptian_address,
    calculate_shipping,
    validate_egyptian_phone,
    normalize_egyptian_phone,
    detect_governorate_from_text,
)


class TestEgyptAddress:

    def test_get_all_governorates(self):
        gov = get_governorates()
        assert len(gov) == 27
        keys = [g["key"] for g in gov]
        assert "cairo" in keys
        assert "giza" in keys
        assert "alexandria" in keys
        assert "dakahlia" in keys  # the previously-missing one

    def test_get_cities_cairo(self):
        cities = get_cities("cairo")
        assert len(cities) > 0
        assert any("قاهرة" in c for c in cities)

    def test_get_cities_invalid_governorate(self):
        cities = get_cities("invalid")
        assert cities == []

    def test_get_areas_cairo(self):
        areas = get_areas_for_governorate("cairo")
        assert len(areas) > 0
        assert any("معادي" in a for a in areas)

    def test_validate_address_valid(self):
        assert validate_egyptian_address("cairo") is True

    def test_validate_address_invalid_governorate(self):
        assert validate_egyptian_address("invalid_governorate") is False

    def test_shipping_inside_cairo(self):
        result = calculate_shipping("cairo", 100)
        assert result["cost"] >= 0
        assert result["governorate"] == "cairo"
        assert result["governorate_ar"] == "القاهرة"

    def test_shipping_outside_cairo(self):
        result = calculate_shipping("alexandria", 100)
        assert result["cost"] >= 0
        assert result["governorate"] == "alexandria"

    def test_free_shipping_above_threshold(self):
        result = calculate_shipping("cairo", 500)
        assert result["cost"] == 0
        assert result["free"] is True

    def test_shipping_unknown_governorate(self):
        result = calculate_shipping("unknown_place", 100)
        assert result["cost"] == 60  # default_outside
        assert result["governorate"] == "unknown_place"


class TestEgyptPhone:

    def test_validate_vodafone_prefix(self):
        assert validate_egyptian_phone("01012345678") is True

    def test_validate_etisalat_prefix(self):
        assert validate_egyptian_phone("01112345678") is True

    def test_validate_orange_prefix(self):
        assert validate_egyptian_phone("01212345678") is True

    def test_validate_we_prefix(self):
        assert validate_egyptian_phone("01512345678") is True

    def test_validate_international_format(self):
        assert validate_egyptian_phone("+201012345678") is True
        assert validate_egyptian_phone("201012345678") is True
        assert validate_egyptian_phone("00201012345678") is True

    def test_validate_invalid_prefix(self):
        assert validate_egyptian_phone("02012345678") is False
        assert validate_egyptian_phone("01612345678") is False

    def test_validate_too_short(self):
        assert validate_egyptian_phone("0101234567") is False

    def test_validate_empty(self):
        assert validate_egyptian_phone("") is False
        assert validate_egyptian_phone(None) is False

    def test_normalize_local(self):
        assert normalize_egyptian_phone("01012345678") == "01012345678"

    def test_normalize_international(self):
        assert normalize_egyptian_phone("+201012345678") == "01012345678"
        assert normalize_egyptian_phone("00201012345678") == "01012345678"

    def test_normalize_with_spaces(self):
        assert normalize_egyptian_phone("010 1234 5678") == "01012345678"

    def test_normalize_invalid_returns_none(self):
        assert normalize_egyptian_phone("invalid") is None


class TestGovernorateDetection:

    def test_detect_arabic_name(self):
        assert detect_governorate_from_text("أنا في القاهرة") == "cairo"

    def test_detect_english_name(self):
        assert detect_governorate_from_text("I live in Alexandria") == "alexandria"

    def test_detect_unknown_returns_none(self):
        assert detect_governorate_from_text("random text") is None
