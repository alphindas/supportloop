"""Pattern rules for prompt injection and for escalating to a human."""

import re
import unicodedata
from pathlib import Path

import yaml

# Invisible characters that can be slipped into words to dodge a pattern.
INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))


def normalise(text: str) -> str:
    """Lower-case, normalise look-alike characters and collapse spaces."""
    text = unicodedata.normalize("NFKC", text).translate(INVISIBLE).replace("’", "'")
    return re.sub(r"[ \t]+", " ", text.lower())


class RuleSet:
    """Named regular expressions loaded from config."""

    def __init__(self, patterns: dict[str, str]) -> None:
        self._rules = {
            name: re.compile(pattern, re.DOTALL | re.MULTILINE)
            for name, pattern in patterns.items()
        }

    def matches(self, text: str) -> list[str]:
        """Names of every rule that matches."""
        cleaned = normalise(text)
        return [name for name, rule in self._rules.items() if rule.search(cleaned)]


def load_guardrails(path: Path) -> tuple[RuleSet, RuleSet]:
    """Return (injection rules, escalation rules)."""
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RuleSet(config["injection_patterns"]), RuleSet(config["escalation_rules"])
