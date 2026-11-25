"""Load versioned prompt templates and fixed messages."""

from dataclasses import dataclass
from pathlib import Path
from string import Template

import yaml


@dataclass(frozen=True)
class PromptTemplate:
    """A system prompt and a user-message template."""

    version: str
    system: str
    user: Template


def load_template(path: Path, version: str) -> PromptTemplate:
    """Read a file that has '### SYSTEM' and '### USER' parts."""
    text = path.read_text(encoding="utf-8")
    try:
        head, user = text.split("### USER\n", 1)
        system = head.split("### SYSTEM\n", 1)[1]
    except (ValueError, IndexError) as error:
        raise ValueError(f"{path.name} needs '### SYSTEM' and '### USER'") from error
    return PromptTemplate(version, system.strip(), Template(user.strip()))


def load_prompt(prompts_dir: Path, version: str) -> PromptTemplate:
    """Read prompt_<version>.txt."""
    return load_template(prompts_dir / f"prompt_{version}.txt", version)


def load_messages(prompts_dir: Path, version: str) -> dict[str, str]:
    """Read the fixed customer-facing messages."""
    path = prompts_dir / f"messages_{version}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))
