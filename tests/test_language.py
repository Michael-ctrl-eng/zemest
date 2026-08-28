"""Tests for Egyptian Arabic / Arabizi / English language detection."""
import pytest

from app.ai.language import detect_language, normalize_arabic


class TestLanguageDetection:

    def test_detect_arabic(self):
        assert detect_language("إيه المنتجات اللي عندكم؟") == "arabic"

    def test_detect_arabic_mixed_with_english(self):
        assert detect_language("عايز أعرف سعر ال product ده") == "arabic"

    def test_detect_arabizi_basic(self):
        # Egyptian Arabizi: 3=ع, 7=ح, 2=ء, 5=خ
        assert detect_language("ana 3ayez el 3aba kam price?") == "arabizi"

    def test_detect_arabizi_with_common_words(self):
        assert detect_language("bhai 3andak keda? yalla 5alas") == "arabizi"

    def test_detect_arabizi_delivery(self):
        assert detect_language("el delivery kobe yewsal? 3andi order") == "arabizi"

    def test_detect_english(self):
        assert detect_language("What products do you have?") == "english"

    def test_detect_english_formal(self):
        assert detect_language("I would like to buy the cotton galabiya please.") == "english"

    def test_detect_empty_string(self):
        assert detect_language("") == "english"

    def test_detect_numbers_only(self):
        assert detect_language("12345") == "english"

    def test_detect_short_arabizi(self):
        # "3ayez" is 1 pattern, "price" is 1 pattern → 2 matches → arabizi
        assert detect_language("3ayez price?") == "arabizi"


class TestNormalizeArabic:

    def test_normalize_strips_tashkeel(self):
        # Arabic with diacritics
        text = "السَّلَامُ عَلَيْكُمْ"
        normalized = normalize_arabic(text)
        assert "ـ" not in normalized  # No tatweel
        # Tashkeel should be removed
        for char in "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652":
            assert char not in normalized

    def test_normalize_alef_variants(self):
        # All alef variants → plain ا
        text = "إأآا"
        normalized = normalize_arabic(text)
        # All characters should be the plain alef ا
        for char in normalized:
            assert char == "ا"

    def test_normalize_taa_marbuta(self):
        # ة → ه
        text = "مدرسة"
        normalized = normalize_arabic(text)
        assert "ه" in normalized
        assert "ة" not in normalized

    def test_normalize_yaa(self):
        # ى → ي
        text = "مصطفى"
        normalized = normalize_arabic(text)
        assert "ي" in normalized
        assert "ى" not in normalized
