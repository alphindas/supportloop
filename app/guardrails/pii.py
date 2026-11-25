"""Remove personal data from text before it is searched, logged, stored or sent to an LLM.

Covers card numbers (Luhn check), IBANs, emails, phone numbers and PIN/CVV-style codes.
It does NOT detect names or postal addresses.
"""

import re
import unicodedata
from dataclasses import dataclass

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

# Two letters, two check digits, then letters/digits, optionally in space-separated groups.
IBAN_CANDIDATE = re.compile(r"\b[A-Za-z]{2}\d{2}(?:[ -]?[A-Za-z0-9]){10,30}\b")
# Length of an IBAN by country code. Matching the exact length avoids redacting
# ordinary text, while still catching an IBAN with a typo in it.
IBAN_LENGTHS = {
    "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20,
    "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26,
    "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
    "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24,
}  # fmt: skip

# 13 to 19 digits, allowing single spaces or dashes between them.
CARD_CANDIDATE = re.compile(r"(?<![\w+])\d(?:[ -]?\d){12,18}(?![\w])")

PHONE_CANDIDATE = re.compile(r"(?<![\w.,/£$€])(?:\+|\()?\d(?:[\d ().-]{6,18})\d(?![\w/]|[.,]\d)")
US_STYLE_PHONE = re.compile(r"\d{3}[ .-]\d{3}[ .-]\d{4}")

# "my pin is 1234", "cvv: 123". The keyword is kept so the question still makes sense.
SECRET_CODE = re.compile(
    r"\b(pin|cvv|cvc|security code|passcode|one[- ]time code|otp)"
    r"(\s*(?:number|code)?\s*(?:is|was|:|=)\s*)(\d{3,8})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Redaction:
    """Redacted text plus how many items of each kind were removed."""

    text: str
    counts: dict[str, int]


def luhn_valid(digits: str) -> bool:
    """The checksum that real card numbers satisfy."""
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _iban_end(candidate: str) -> int | None:
    """Return where the IBAN ends inside the match, or None if it is not an IBAN."""
    wanted = IBAN_LENGTHS.get(candidate[:2].upper())
    if wanted is None:
        return None
    seen = 0
    for index, char in enumerate(candidate):
        if char.isalnum():
            seen += 1
            if seen == wanted:
                following = candidate[index + 1 : index + 2]
                # A longer unbroken run of characters is something else.
                return None if following.isalnum() else index + 1
    return None


def _looks_like_phone(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    if not 9 <= len(digits) <= 15:
        return False
    return candidate.startswith(("+", "(", "0")) or bool(US_STYLE_PHONE.fullmatch(candidate))


def redact(text: str) -> Redaction:
    """Replace personal data with placeholders such as [EMAIL]."""
    # NFKC turns look-alike characters (e.g. full-width digits) into normal ones.
    text = unicodedata.normalize("NFKC", text)
    counts: dict[str, int] = {}

    def mark(kind: str) -> str:
        counts[kind] = counts.get(kind, 0) + 1
        return f"[{kind}]"

    def replace_iban(match: re.Match[str]) -> str:
        found = match.group(0)
        end = _iban_end(found)
        return found if end is None else mark("IBAN") + found[end:]

    def replace_card(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        return mark("CARD_NUMBER") if luhn_valid(digits) else match.group(0)

    def replace_phone(match: re.Match[str]) -> str:
        return mark("PHONE") if _looks_like_phone(match.group(0)) else match.group(0)

    # Order matters: the most specific patterns run first, so that a card number is
    # not half-eaten by the phone pattern.
    text = EMAIL.sub(lambda _: mark("EMAIL"), text)
    text = IBAN_CANDIDATE.sub(replace_iban, text)
    text = CARD_CANDIDATE.sub(replace_card, text)
    text = PHONE_CANDIDATE.sub(replace_phone, text)
    text = SECRET_CODE.sub(lambda m: m.group(1) + m.group(2) + mark("SECRET_CODE"), text)
    return Redaction(text, counts)
