"""Guardrails integration.

NeMo Guardrails owns inbound and outbound conversational rail decisions. The
project owns citation grounding because that check is a join against our
stable passage identifiers and does not belong in a model-driven rail.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).with_name("config")


class GuardrailsUnavailableError(RuntimeError):
    """Raised when NeMo Guardrails is not installed or cannot load its config."""


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    name: str
    allowed: bool
    reason: str
    redacted_text: str


def _rails() -> Any:
    if sys.version_info >= (3, 14):
        raise GuardrailsUnavailableError(
            "NeMo Guardrails 0.17.0 is not compatible with Python 3.14; "
            "run this project with Python 3.12 or 3.13"
        )
    try:
        from nemoguardrails import LLMRails, RailsConfig  # type: ignore[import-untyped]
    except ImportError as exc:
        raise GuardrailsUnavailableError(
            "NeMo Guardrails is required for inbound and outbound checks; "
            "install the project's guardrails extra"
        ) from exc
    try:
        content = (CONFIG_PATH / "config.yml").read_text(encoding="utf-8")
        missing: list[str] = []

        def resolve(match: re.Match[str]) -> str:
            name = match.group(1)
            value = os.environ.get(name)
            if not value:
                missing.append(name)
                return match.group(0)
            return value

        content = re.sub(r"\$\{([A-Z0-9_]+)\}", resolve, content)
        if missing:
            raise GuardrailsUnavailableError(
                "missing NeMo configuration variables: " + ", ".join(sorted(set(missing)))
            )
        return LLMRails(RailsConfig.from_content(yaml_content=content))
    except GuardrailsUnavailableError:
        raise
    except Exception as exc:  # NeMo exposes several config-time exception types.
        raise GuardrailsUnavailableError(f"could not load NeMo rail config: {exc}") from exc


async def check_input(text: str) -> GuardrailResult:
    """Run the configured NeMo input rails; fail closed on adapter failure."""
    try:
        rails = _rails()
        await rails.generate_async(messages=[{"role": "user", "content": text}])
    except GuardrailsUnavailableError as exc:
        return GuardrailResult("nemo_input", False, str(exc), text)
    except Exception as exc:
        return GuardrailResult("nemo_input", False, f"NeMo input rail failed: {exc}", text)
    return GuardrailResult("nemo_input", True, "NeMo input rails accepted the request", text)


async def check_output(text: str) -> GuardrailResult:
    """Run the configured NeMo output rails; grounding is checked separately."""
    try:
        rails = _rails()
        await rails.generate_async(messages=[{"role": "assistant", "content": text}])
    except GuardrailsUnavailableError as exc:
        return GuardrailResult("nemo_output", False, str(exc), text)
    except Exception as exc:
        return GuardrailResult("nemo_output", False, f"NeMo output rail failed: {exc}", text)
    return GuardrailResult("nemo_output", True, "NeMo output rails accepted the response", text)


def allow_output(text: str, *, citations_verified: bool) -> GuardrailResult:
    if not citations_verified:
        return GuardrailResult(
            "grounding", False, "one or more citations could not be verified", text
        )
    return GuardrailResult("grounding", True, "citations verified", text)
