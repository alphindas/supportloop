"""PII redaction. All numbers here are published test values or made up."""

import pytest

from app.guardrails.pii import luhn_valid, redact


@pytest.mark.parametrize(
    "card",
    ["4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111", "378282246310005"],
)
def test_card_numbers_are_removed(card: str) -> None:
    result = redact(f"my card {card} was declined")
    assert result.text == "my card [CARD_NUMBER] was declined"
    assert result.counts == {"CARD_NUMBER": 1}


def test_full_width_digits_do_not_bypass_redaction() -> None:
    full_width = "4111111111111111".translate({ord(str(d)): 0xFF10 + d for d in range(10)})
    assert redact(full_width).text == "[CARD_NUMBER]"


def test_numbers_that_fail_luhn_are_not_called_cards() -> None:
    assert not luhn_valid("4111111111111112")
    assert "CARD_NUMBER" not in redact("reference 4111111111111112").counts


@pytest.mark.parametrize(
    "iban",
    [
        "GB82WEST12345698765432",
        "GB82 WEST 1234 5698 7654 32",
        "de89 3704 0044 0532 0130 00",
        "FR1420041010050500013M02606",
    ],
)
def test_ibans_are_removed(iban: str) -> None:
    assert redact(f"send it to {iban} please").text == "send it to [IBAN] please"


def test_iban_followed_by_words_keeps_the_words() -> None:
    assert redact("GB82WEST12345698765432 is mine").text == "[IBAN] is mine"


def test_emails_are_removed() -> None:
    assert redact("write to jo.smith+nova@mail.example.co.uk.").text == "write to [EMAIL]."


@pytest.mark.parametrize(
    "phone",
    ["+44 7700 900123", "07700 900123", "07700900123", "(020) 7946 0958", "555-123-4567"],
)
def test_phone_numbers_are_removed(phone: str) -> None:
    assert redact(f"call me on {phone} today").text == "call me on [PHONE] today"


def test_pin_and_cvv_values_are_removed_but_the_question_survives() -> None:
    assert redact("my PIN is 4821, change it").text == "my PIN is [SECRET_CODE], change it"
    assert redact("cvv: 123").text == "cvv: [SECRET_CODE]"


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ("cvv 913 keeps failing", "cvv [SECRET_CODE] keeps failing"),
        ("my pin 4821 is blocked", "my pin [SECRET_CODE] is blocked"),
        ("OTP code 55210", "OTP code [SECRET_CODE]"),
    ],
)
def test_codes_are_removed_without_a_joining_word(raw: str, cleaned: str) -> None:
    assert redact(raw).text == cleaned


@pytest.mark.parametrize(
    "text",
    [
        "I entered the wrong PIN 3 times",
        "it asks for my PIN after £300 of payments",
        "my passcode has 6 digits",
        "I was charged £1,000.00 twice on 2026-11-25",
        "I made 3 payments of 250 on 01/02/2026 at 10:45",
        "Can I top up 10000 or 30000 in 30 days?",
        "it has been 5 to 7 working days",
        "how do I change my PIN?",
    ],
)
def test_ordinary_text_is_left_alone(text: str) -> None:
    assert redact(text) == redact(text).__class__(text, {})


def test_several_items_are_all_counted() -> None:
    result = redact("a@b.com, c@d.org and 4111 1111 1111 1111")
    assert result.counts == {"EMAIL": 2, "CARD_NUMBER": 1}
