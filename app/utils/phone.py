import re


def validate_egyptian_phone(phone: str) -> bool:
    """Validate an Egyptian phone number.

    Valid formats:
    - 01XXXXXXXXX (11 digits, starts with 01)
    - +201XXXXXXXXX
    - 201XXXXXXXXX
    """
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)

    if re.match(r'^01[0125]\d{8}$', cleaned):
        return True
    if re.match(r'^201[0125]\d{8}$', cleaned):
        return True

    return False


def normalize_egyptian_phone(phone: str) -> str:
    """Normalize an Egyptian phone number to 01XXXXXXXXX format."""
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)

    if cleaned.startswith("20"):
        cleaned = "0" + cleaned[2:]

    return cleaned
