"""Check what each money amount in a reply is said to be.

The number check asks only whether an amount appears in a cited article. This one reads the
words around the amount (fee, minimum or limit; which period, product and card) and compares
them with the facts about that amount in config/money_facts.yaml.

It is a set of word patterns, not language understanding. When it cannot tell what a clause
says, it stays silent, and the number check is then the only protection.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Fact:
    """One amount in one article."""

    value: str
    role: str
    topics: frozenset[str]
    period: str | None = None
    card: str | None = None


@dataclass(frozen=True)
class Claim:
    """What a reply says about one amount. None or empty means the reply did not say."""

    value: str
    role: str | None
    topics: frozenset[str]
    period: str | None
    cards: frozenset[str]


AMOUNT = re.compile(r"£\s?\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?\s?%")
OUTSIDE = re.compile(
    r"(?:issued )?outside (?:of )?(?:the )?(?:uk|eea)(?:,? (?:and|or) (?:the )?(?:eea|uk))?"
    r"|non[- ](?:uk|eea)(?:(?:/| and | or )(?:non[- ])?(?:uk|eea))?"
)
CARDS = {
    "outside_uk_eea": r"\boutsidecard\b",
    "credit": r"\bcredit cards?\b",
    "home_debit": r"\b(?:uk|eea)(?:[- ]issued)?(?: (?:and|or) (?:the )?(?:uk|eea))? debit\b",
}
TOPICS = {
    "card_topup": r"\bcard top[- ]?ups?\b|\bby card\b"
    r"|\btop(?:ping|s)?[- ]?up (?:by|with)(?: a)? card\b",
    "cash": r"\bcash deposits?\b|\b(?:adding|add|deposit(?:ing)?) cash\b",
    "bank_transfer": r"\bbank transfers?\b",
    "swift": r"\bswift\b|\binternational (?:bank )?transfers?\b",
    "sepa": r"\bsepa\b",
    "withdrawal": r"\bwithdr[ae]w\w*|\bcash machines?\b|\batms?\b",
    "express": r"\bexpress\b",
    "spare": r"\b(?:spare|second) (?:physical )?card\b",
    "replacement": r"\breplacement\b",
    "contactless": r"\bcontactless\b",
    "weekend": r"\bweekends?\b",
    "exchange": r"\bexchang\w+",
    "card_payment": r"\bcard payment limit\b",
}
PERIODS = {
    "30days": r"\b30[- ]days?\b",
    "day": r"\bper day\b|\ba day\b|\bdaily\b|\beach day\b|\b(?:in )?one day\b",
    "month": r"\bmonth(?:ly)?\b",
    "single": r"\bsingle\b|\bper (?:top[- ]?up|transaction|deposit|payment)\b"
    r"|\beach (?:top[- ]?up|deposit|payment)\b|\bone top[- ]?up\b",
}
# Cues before an amount. The one nearest to the amount wins.
ROLE_BEFORE = {
    "min_fee": r"\bmin(?:imum|\.)? (?:fee|charge)\b",
    "min": r"\bminimum\b|\bat least\b|\bsmallest\b|\blowest\b"
    r"|\bno less than\b|\bfrom as little as\b",
    "max": r"\bmaximum\b|\bup to\b|\bat most\b|\bno more than\b|\blimit(?:s|ed)?\b|\bcapped\b"
    r"|\blargest\b|\bthe most\b",
    "threshold": r"\bover\b|\babove\b|\bmore than\b|\bexceed\w*\b|\bbeyond\b|\bafter\b",
    "fee": r"\bfees?\b|\bcharg(?:e|es|ed|ing)\b|\bcosts?\b|\bmarkup\b|\bpay(?:s)?\b",
}
# Words straight after an amount, as in "a £10 minimum fee". These win over earlier cues.
ROLE_AFTER = [
    ("min_fee", r"^\s*min(?:imum|\.)? (?:fee|charge)\b"),
    ("min", r"^\s*minimum\b"),
    ("max", r"^\s*(?:maximum|limit)\b"),
    ("fee", r"^(?:\s*(?:weekend|flat|card|top[- ]?up|exchange))?\s*(?:fee|charge|markup)\b"),
]
ACCEPTS = {
    "fee": {"fee"},
    "min": {"min", "min_fee"},
    "max": {"max", "allowance"},
    "min_fee": {"min_fee"},
    "threshold": {"threshold", "allowance"},
}
FREE = re.compile(r"\bfree\b|\bno (?:\w+ )?(?:fee|charge)\b")
NEGATION = re.compile(r"\bnot\b|\bno\b|n't\b")
CLAUSE_BREAK = re.compile(
    r";|, (?=and |but |while |whereas |or )|, | but | while | whereas "
    r"| and (?=(?:a |an |the )?(?:\w+ )?(?:cards?|credit|debit|express|cash|bank|swift|sepa)\b)"
)


def load_facts(path: Path) -> dict[str, list[Fact]]:
    """Read the facts file: article id -> facts."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        article: [Fact(**{**item, "topics": frozenset(item["topics"])}) for item in items]
        for article, items in raw.items()
    }


def canonical(amount: str) -> str:
    """'£5,000' and '£5000' are equal; so are '2%' and '2.0%'."""
    text = amount.replace(" ", "").replace(",", "")
    sign, number = ("£", text[1:]) if text.startswith("£") else ("%", text.rstrip("%"))
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return f"£{number}" if sign == "£" else f"{number}%"


def _normalise(text: str) -> str:
    cleaned = text.lower().replace("*", "").replace("’", "'")
    # One token, so that its "and" never splits a clause and "uk" is not read as a UK card.
    return OUTSIDE.sub("outsidecard", cleaned)


def sentences(text: str) -> list[str]:
    """Split on line breaks and sentence ends. '2.0%' has no space, so it stays whole."""
    return [s.strip() for s in re.split(r"\n+|(?<=[.!?])\s+", _normalise(text)) if s.strip()]


def _found(patterns: dict[str, str], text: str) -> frozenset[str]:
    return frozenset(name for name, pattern in patterns.items() if re.search(pattern, text))


def _period(clause: str, sentence: str) -> str | None:
    for scope in (clause, sentence):
        hits = _found(PERIODS, scope)
        if len(hits) == 1:
            return next(iter(hits))
        if hits:
            return None  # two periods in one place: do not guess
    return None


def _role(before: str, after: str) -> str | None:
    for role, pattern in ROLE_AFTER:
        if re.search(pattern, after):
            return role
    best: tuple[int, int, str] | None = None
    for role, pattern in ROLE_BEFORE.items():
        for match in re.finditer(pattern, before):
            candidate = (match.end(), match.end() - match.start(), role)
            if best is None or candidate > best:
                best = candidate
    return best[2] if best else None


def extract_claims(sentence: str) -> list[Claim]:
    """One claim per amount in an already normalised sentence."""
    claims = []
    for clause in CLAUSE_BREAK.split(sentence):
        matches = list(AMOUNT.finditer(clause))
        for index, match in enumerate(matches):
            start = matches[index - 1].end() if index else 0
            end = matches[index + 1].start() if index + 1 < len(matches) else len(clause)
            before, after = clause[start : match.start()], clause[match.end() : end]
            role = _role(before, after)
            if re.search(r"\bbetween\s*$", before):
                role = "min"
            elif index and re.search(r"\bbetween\b", clause[: matches[index - 1].start()]):
                role = "max"
            if re.search(r"\b(?:no|not)\b[^.]{0,12}$", before) and "no more than" not in before:
                role = None  # "there is no £10 fee"
            # "the fee is 1.5%, or £10 minimum, whichever is higher" states a minimum FEE.
            if role == "min" and "whichever" in sentence:
                role = "min_fee" if re.search(ROLE_BEFORE["fee"], sentence) else role
            claims.append(
                Claim(
                    canonical(match.group()),
                    role,
                    _found(TOPICS, clause) or _found(TOPICS, sentence),
                    _period(clause, sentence),
                    _found(CARDS, clause),
                )
            )
    return claims


def _conflicts(claim: Claim, fact: Fact) -> list[str]:
    """Why this fact does not support this claim."""
    reasons = []
    if claim.role and fact.role not in ACCEPTS[claim.role]:
        reasons.append("role")
    if claim.period and fact.period and claim.period != fact.period:
        reasons.append("period")
    if claim.topics and not claim.topics & fact.topics:
        reasons.append("topic")
    if claim.cards and fact.card:
        # A card issued outside the UK and EEA pays the higher fee, whatever its type.
        expected = "outside_uk_eea" if "outside_uk_eea" in claim.cards else None
        if (expected and fact.card != expected) or (not expected and fact.card not in claim.cards):
            reasons.append("card")
    return reasons


def _card_rules(sentence: str) -> list[str]:
    """Top-up card rules that have no amount of their own to compare."""
    problems = []
    for clause in CLAUSE_BREAK.split(sentence):
        cards = _found(CARDS, clause)
        free = FREE.search(clause)
        charged = cards & {"outside_uk_eea", "credit"} and "home_debit" not in cards
        says_free = free and not NEGATION.search(clause[: free.start()])
        if charged and says_free and not AMOUNT.search(clause):
            problems.append("a card with a top-up fee is called free")
        gives_fee = AMOUNT.search(clause) and re.search(r"\bfee|charg|cost|pay", clause)
        if cards == {"home_debit"} and gives_fee and not NEGATION.search(clause):
            problems.append("a UK or EEA debit card is given a fee")
    amounts = {canonical(m.group()) for m in AMOUNT.finditer(sentence)}
    if (
        {"1.5%", "2%"} <= amounts
        and re.search(r"\bboth\b|\bplus\b|\bon top\b|\bin addition\b|\bcombined\b", sentence)
        and "outsidecard" in sentence
        and not re.search(r"\bonly\b|\bhigher\b|\bnot both\b", sentence)
    ):
        problems.append("two top-up card fees are added together")
    return problems


def claim_problems(answer: str, cited: list[str], facts: dict[str, list[Fact]]) -> list[str]:
    """Claims in the answer that the cited articles' facts do not support.

    An amount with no fact in any cited article is left to the number check.
    """
    known = [fact for article in cited for fact in facts.get(article, [])]
    problems = []
    for sentence in sentences(answer):
        if "topup-fees" in cited:
            problems += _card_rules(sentence)
        for claim in extract_claims(sentence):
            same_value = [f for f in known if canonical(f.value) == claim.value]
            if not same_value:
                continue
            reasons = [_conflicts(claim, fact) for fact in same_value]
            if all(reasons):
                why = ", ".join(sorted(min(reasons, key=len)))
                problems.append(f"{claim.value} does not match the article ({why})")
    return list(dict.fromkeys(problems))
