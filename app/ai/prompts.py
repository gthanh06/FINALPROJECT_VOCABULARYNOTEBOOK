# app/ai/prompts.py — loads the prompts kept in prompts/*.md.
#
# File format (see prompts/lookup.md):
#   version: 1            bump it after changing the prompt, so cached answers are redone
#   === system ===
#   instructions for the model
#   === user ===
#   the request, with $placeholders filled by render()
# $placeholders use string.Template, so JSON braces in a prompt need no escaping.
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: Template


@cache
def load(name: str) -> Prompt:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    head, rest = text.split("=== system ===", 1)
    system, user = rest.split("=== user ===", 1)
    version = ""
    for line in head.splitlines():
        if line.lower().startswith("version:"):
            version = line.split(":", 1)[1].strip()
    if not version:
        raise ValueError(f"prompts/{name}.md has no 'version:' line")
    return Prompt(name, version, system.strip(), Template(user.strip()))


def render(name: str, **values: object) -> tuple[str, str]:
    """Returns (system instruction, user message) with the placeholders filled."""
    prompt = load(name)
    return prompt.system, prompt.user.substitute({k: str(v) for k, v in values.items()})
