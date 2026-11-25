"""Build evals/sets/retrieval_v1.jsonl (run once; the output is versioned in git).

Real messages were drawn at random (seed 20261125, one per covered intent) from the
eval pool, then labelled by reading each one. All labels and all AI-written questions
are 'ai_drafted' until a human marks them reviewed with scripts/review_pairs.py.

The script refuses to overwrite an existing file, so human review marks are not lost.

Negative questions have no expected article. They are used to calibrate and report the
escalation threshold. They deliberately avoid the planted KB gaps, so that tuning
cannot learn where those gaps are.
"""

import json
import sys

from app.banking77 import read_messages
from app.config import PROJECT_ROOT

OUTPUT = PROJECT_ROOT / "evals" / "sets" / "retrieval_v1.jsonl"

# (split, Banking77 row number, expected article)
REAL = """
test 1104 unrecognised-card-payment
test 1713 request-refund
test 236 cash-withdrawal-pending
test 2536 virtual-card
test 2319 transfer-failed
test 1294 card-acceptance
test 2080 card-payment-reversed
test 1160 verify-identity
test 1022 topup-reverted
test 1805 declined-card-payment
test 313 card-delivery-times
test 2728 cash-withdrawal-unrecognised
test 2221 transfer-fees
test 2944 card-expiry
test 898 supported-cards-currencies
test 2182 beneficiary-not-allowed
test 2511 country-support
test 2646 topup-failed
test 860 transfer-not-received
test 815 extra-statement-charge
test 144 foreign-payment-wrong-rate
test 478 lost-or-stolen-card
test 96 exchange-rates
test 1762 refund-not-showing
test 41 link-card
test 3014 verify-identity
test 540 card-pin
test 9 card-delivery-times
test 1587 cash-withdrawal-declined
test 2428 spare-card
test 1725 transfer-failed
test 1603 card-payment-pending
test 3073 country-support
test 426 exchange-currency
dev 2132 card-pin
dev 2899 cash-withdrawals
dev 690 cancel-transfer
dev 1229 verification-problems
dev 1521 passcode-reset
dev 1401 compromised-card
dev 724 topup-limits
dev 2566 foreign-payment-wrong-rate
dev 2398 topup-verification
dev 2839 topup-fees
dev 1964 charged-twice
dev 761 cash-wrong-amount
dev 1324 topup-by-card
dev 1063 cash-deposit-missing
dev 2339 topup-by-bank-transfer
dev 179 extra-statement-charge
dev 669 topup-pending
"""

EXCLUDED = {
    632: "'transfer policy' could mean fees, timing or limits",
    1491: "'weird charges' does not point to one article",
    586: "asks the price of a new card, but the dataset labels it contactless_not_working",
}

# AI-written, single expected article. Written to avoid copying article wording.
WRITTEN_SINGLE = {
    "test": [
        (
            "the shop till said no when i held my card near it, the chip works though",
            "contactless-payments",
        ),
        ("how much can i take out of a cash machine in one day", "cash-withdrawals"),
        (
            "sending dollars to a friend's bank in the US, what's it going to cost me",
            "transfer-fees",
        ),
        (
            "is it cheaper to swap pounds for euros on a Saturday or during the week",
            "exchange-fees",
        ),
        ("you're asking for payslips, why and what else can I send", "source-of-funds"),
        (
            "someone on the phone told me to move my savings to a safe account",
            "account-security-tips",
        ),
        (
            "the hotel took way more than my room cost and it's still sitting there",
            "card-payment-pending",
        ),
        (
            "i never got the goods and the seller is ignoring me, can you get my money back",
            "disputes-chargebacks",
        ),
        ("what do my employer need so they can pay my wages in", "receiving-money"),
        ("I put forty quid in at the shop counter and nothing's shown up", "cash-deposit-missing"),
        ("can I pay money in with a cheque", "topup-by-cash"),
        ("my new plastic came in the post, now what", "activate-card"),
        ("what's the most I can load from another card in a month", "topup-limits"),
        ("how do i pay someone who banks with a different company", "send-money"),
        ("pump at the petrol station wont take my card but shops do", "card-acceptance"),
        ("how long till money I send to Germany gets there", "transfer-timing"),
    ],
    "dev": [
        (
            "there's a weird 4 digit number on my other bank statement from you",
            "topup-verification",
        ),
        ("my selfie check keeps getting rejected", "verification-problems"),
        ("i sent cash to the wrong person by accident, can it be stopped", "cancel-transfer"),
        ("I want a card just for online shopping without waiting for the post", "virtual-card"),
        ("which ways can i get money into this thing", "topup-methods"),
        ("my transfer says scheduled and nothing is happening", "transfer-pending"),
        (
            "the machine at the airport asked if i wanted to be charged in pounds and the rate was awful",
            "foreign-payment-wrong-rate",
        ),
        ("do you do bitcoin", "supported-cards-currencies"),
    ],
}

# AI-written questions that need more than one article.
WRITTEN_MULTI = {
    "test": [
        (
            "my card was nicked and there's a payment on there that wasn't me",
            ["lost-or-stolen-card", "unrecognised-card-payment"],
        ),
        (
            "what does it cost to add money with a credit card and how much can I add per day",
            ["topup-fees", "topup-limits"],
        ),
        (
            "how long does an international transfer take and what's the fee",
            ["transfer-timing", "transfer-fees"],
        ),
        (
            "my pin is blocked and also contactless stopped working",
            ["card-pin", "contactless-payments"],
        ),
        (
            "can I get a virtual card now while I wait for the real one, and when will that arrive",
            ["virtual-card", "card-delivery-times"],
        ),
        (
            "what rate do you use for euros and is there any fee for exchanging",
            ["exchange-rates", "exchange-fees"],
        ),
        (
            "I want a second card, how much is it and how long will delivery take",
            ["spare-card", "card-delivery-times"],
        ),
        (
            "I was charged twice and one of the shops promised a refund that never came",
            ["charged-twice", "refund-not-showing"],
        ),
        (
            "do you charge to take cash out abroad and what exchange rate do I get",
            ["cash-withdrawals", "exchange-rates"],
        ),
        (
            "my transfer got declined, is it because you haven't checked where my money is from",
            ["transfer-failed", "source-of-funds"],
        ),
    ],
    "dev": [
        ("how do I check who I am with you and why do you even need that", ["verify-identity"]),
        (
            "top up is stuck, and if it fails will the money go back",
            ["topup-pending", "topup-failed"],
        ),
        (
            "I forgot my passcode and I'm worried someone got into my account",
            ["passcode-reset", "account-security-tips"],
        ),
        ("I need to see my PIN and switch on my new card", ["card-pin", "activate-card"]),
        ("can I load cash at a shop, and what's the fee", ["topup-by-cash", "topup-fees"]),
    ],
}

NEGATIVE_BANKING = {
    "test": [
        "what interest do you pay on savings",
        "can I apply for a personal loan",
        "do you offer an arranged overdraft",
        "can my partner and I open a joint account",
        "I want to buy shares through the app",
        "do you have accounts for limited companies",
        "is there cashback on my purchases",
        "can I get travel insurance with my account",
        "will this account affect my credit score",
        "do you offer mortgages",
    ],
    "dev": [
        "is there a referral bonus if I invite a friend",
        "can I get a credit card from you with a borrowing limit",
        "can I set up a savings pot with a goal",
        "can you give me a yearly tax statement",
        "can I pay my council tax in instalments through you",
        "do you offer car finance",
        "can I buy gold in the app",
        "do you sell pension plans",
    ],
}

NEGATIVE_OFFTOPIC = {
    "test": [
        "what's the weather like in London tomorrow",
        "write me a poem about the sea",
        "who won the football last night",
        "how do I cook a risotto",
        "can you help me with my python homework",
        "what is the capital of Australia",
        "recommend me a film for tonight",
        "my wifi router keeps disconnecting",
        "translate good morning into Japanese",
        "how many calories are in a banana",
    ],
    "dev": [
        "tell me a joke",
        "what time does the nearest pharmacy close",
        "give me directions to the train station",
        "who is the prime minister of Canada",
        "how do I fix a flat bicycle tyre",
        "what should I get my mum for her birthday",
        "explain how vaccines work",
    ],
}


def build_rows() -> list[dict]:
    """Assemble all rows with provenance."""
    messages = {
        int(m.message_id.rsplit("-", 1)[1]): m
        for m in read_messages(PROJECT_ROOT / "data" / "banking77" / "test.csv")
    }
    rows: list[dict] = []

    def add(split, question, expected, kind, source, message_id=None, intent=None):
        rows.append(
            {
                "id": f"ret-{len(rows) + 1:03d}",
                "split": split,
                "question": question,
                "expected_article_ids": expected,
                "kind": kind,
                "source": source,
                "source_message_id": message_id,
                "intent": intent,
                "labelled_by": "ai",
                "review_status": "ai_drafted",
                "added_in_version": "v1",
            }
        )

    for line in REAL.split("\n"):
        if line.strip():
            split, number, article = line.split()
            message = messages[int(number)]
            add(split, message.text, [article], "single", "banking77_eval_pool",
                message.message_id, message.intent)  # fmt: skip
    for split in ("test", "dev"):
        for question, article in WRITTEN_SINGLE[split]:
            add(split, question, [article], "single", "ai_written")
        for question, articles in WRITTEN_MULTI[split]:
            kind = "multi" if len(articles) > 1 else "single"
            add(split, question, articles, kind, "ai_written")
        for question in NEGATIVE_BANKING[split]:
            add(split, question, [], "negative_banking", "ai_written")
        for question in NEGATIVE_OFFTOPIC[split]:
            add(split, question, [], "negative_offtopic", "ai_written")
    return rows


def main() -> None:
    """Write the file, unless it already exists."""
    if OUTPUT.exists():
        sys.exit(f"{OUTPUT.name} already exists. New questions go in a new version.")
    rows = build_rows()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    OUTPUT.with_suffix(".excluded.json").write_text(
        json.dumps({f"b77-test-{k}": v for k, v in EXCLUDED.items()}, indent=2) + "\n"
    )
    for split in ("test", "dev"):
        subset = [r for r in rows if r["split"] == split]
        positive = [r for r in subset if r["expected_article_ids"]]
        print(
            f"{split}: {len(positive)} with an expected article "
            f"({sum(r['source'] == 'banking77_eval_pool' for r in positive)} real, "
            f"{sum(r['kind'] == 'multi' for r in positive)} multi-article), "
            f"{len(subset) - len(positive)} negative"
        )


if __name__ == "__main__":
    main()
