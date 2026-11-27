"""Collect fresh phi4-mini replies to money questions, for the fee check comparison.

The questions were written by Claude Code (not reviewed by a human) after the claim check
was committed. The claim check is switched OFF here, so replies are not changed by it.

Usage: uv run python -m evals.fee_replies   (needs Ollama; no Groq quota, no database)
"""

import asyncio
import json

import httpx

from app.chat.factory import build_chat_service
from app.config import PROJECT_ROOT, get_settings
from app.guardrails.output import parse_bot_answer

OUTPUT = PROJECT_ROOT / "reports" / "raw" / "fee_replies_phi4-mini.json"
QUESTIONS = [
    "How much does it cost to add money with my debit card from France?",
    "I have an American card. What will I pay to top up with it?",
    "Is there a charge for using a credit card to load my account?",
    "My credit card is from Canada, what fee applies when I top up?",
    "What's the least I can top up by card?",
    "How much can I put on my account by card in one go?",
    "Is there a daily cap on card top-ups?",
    "How much can I add by card over a month?",
    "Can I send any amount to top up by bank transfer?",
    "What does it cost to pay in cash?",
    "What is the smallest and largest cash deposit?",
    "Do you charge me for taking money out of a cash machine?",
    "How much cash can I withdraw for free each month?",
    "What is the most cash I can take out in a day?",
    "I've already made five withdrawals this month. What happens on the next one?",
    "What do you charge to send money abroad by SWIFT?",
    "Is a SEPA transfer free?",
    "Does it cost anything to send money to a friend who uses NovaPay?",
    "What's the fee for exchanging 2000 pounds in a month?",
    "Is it more expensive to exchange money on Saturday?",
    "How much can I exchange before a fee applies?",
    "What is the limit for a contactless payment?",
    "Why did my card ask for a PIN after several tap payments?",
    "How much is express delivery for a new card?",
    "Do I have to pay for my first card?",
    "What does a second card cost?",
    "My card was stolen. How much is a new one?",
    "I want to switch from Visa to Mastercard. Is there a cost?",
    "What is the daily limit for card payments?",
    "Will a large bank transfer be checked?",
    "List all the fees for adding money.",
    "What are your cash withdrawal fees and limits?",
    "Tell me the card top-up limits and fees.",
    "What fees apply at the weekend if I've used up my exchange allowance?",
    "Are UK bank transfers free both in and out?",
    "How much does it cost to replace a card?",
]


async def collect() -> dict:
    """One reply per question, each in a new conversation."""
    settings = get_settings().model_copy(
        update={
            "llm_provider": "ollama",
            "retrieval_device": "cpu",
            "llm_cache_enabled": False,
            "fee_check_enabled": False,
        }
    )
    rows = []
    async with httpx.AsyncClient(timeout=300) as client:
        service = build_chat_service(settings, client)
        for number, question in enumerate(QUESTIONS, start=1):
            result, trace = await service.handle("fee-replies", f"q-{number}", question)
            parsed = parse_bot_answer(trace.model_reply or "")
            rows.append(
                {
                    "id": f"phi-{number:02d}",
                    "question": question,
                    "reply": parsed.answer if parsed else "",
                    "model_behavior": parsed.behavior if parsed else None,
                    "cited": parsed.cited_article_ids if parsed else [],
                    "context": trace.context,
                    "final_behavior": result.behavior,
                    "guardrail_events": result.guardrail_events,
                }
            )
            print(f"{number}/{len(QUESTIONS)}", flush=True)
    return {"model": f"ollama:{settings.ollama_model}", "rows": rows}


def main() -> None:
    """Save the replies once. Delete the file to collect them again."""
    if OUTPUT.exists():
        raise SystemExit(f"{OUTPUT.name} exists; its labels belong to these exact replies.")
    OUTPUT.write_text(json.dumps(asyncio.run(collect()), indent=1, ensure_ascii=False) + "\n")
    print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
