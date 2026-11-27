"""The claim check, on phrasings written from the articles and the two development cases.

These are not the frozen test cases (evals/sets/fee_claims_v1.yaml)."""

import pytest

from app.config import PROJECT_ROOT
from app.guardrails.claims import AMOUNT, canonical, claim_problems, load_facts
from app.rag.kb import load_articles

FACTS = load_facts(PROJECT_ROOT / "config" / "money_facts.yaml")
ARTICLES = {a.id: a.body for a in load_articles(PROJECT_ROOT / "data" / "kb")}


def test_every_article_amount_has_a_fact_and_the_reverse() -> None:
    for article_id, body in ARTICLES.items():
        in_text = {canonical(m.group()) for m in AMOUNT.finditer(body)}
        in_facts = {canonical(f.value) for f in FACTS.get(article_id, [])}
        assert in_text == in_facts, article_id
    assert set(FACTS) <= set(ARTICLES)


@pytest.mark.parametrize(
    ("answer", "cited"),
    [
        # Development cases: replies from reports/local_model_fee_cases.md.
        ("The fee for topping up by card is 1.5% of the amount, or £10 minimum, whichever "
         "is higher.", "topup-fees topup-limits"),
        ("For card top-ups, the fee is 1.5% of the amount if the card is a UK debit card or "
         "an EEA debit card.", "topup-fees"),
        ("Express delivery has a £5 fee.", "order-physical-card spare-card"),
        ("You can withdraw up to £200 per day.", "cash-withdrawals"),
    ],
)  # fmt: skip
def test_wrong_claims_are_reported(answer: str, cited: str) -> None:
    assert claim_problems(answer, cited.split(), FACTS)


@pytest.mark.parametrize(
    ("answer", "cited"),
    [
        ("UK and EEA debit cards have no fee, credit cards incur a 1.5% fee, and cards issued "
         "outside the UK and EEA have a 2.0% fee. Cash deposits also have a 1.5% fee.",
         "topup-fees"),
        ("Top-up limits are £10 minimum, £5,000 maximum per top-up, £10,000 maximum per day, "
         "and £30,000 maximum in any 30 days.", "topup-limits"),
        ("Each cash deposit must be between £5 and £500.", "topup-limits"),
        ("A spare card costs £5.", "spare-card"),
        ("There is no £10 fee.", "topup-limits"),
        ("Your amount of £42 is shown in the app.", "topup-fees"),
    ],
)  # fmt: skip
def test_supported_claims_pass(answer: str, cited: str) -> None:
    assert claim_problems(answer, cited.split(), FACTS) == []
