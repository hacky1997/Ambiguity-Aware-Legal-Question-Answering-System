"""Microsoft Presidio adapter for personal-data minimization."""

from __future__ import annotations

from dataclasses import dataclass


class PrivacyUnavailableError(RuntimeError):
    """Raised when the Presidio optional extra is not installed."""


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    entities: tuple[str, ...]


def redact_personal_data(text: str, *, language: str = "en") -> RedactionResult:
    """Analyze and anonymize text with Microsoft Presidio."""
    try:
        from presidio_analyzer import AnalyzerEngine  # type: ignore[import-not-found]
        from presidio_anonymizer import AnonymizerEngine  # type: ignore[import-not-found]
    except ImportError as exc:
        raise PrivacyUnavailableError(
            "Presidio is required for personal-data detection; install the privacy extra"
        ) from exc

    analyzer = AnalyzerEngine()
    findings = analyzer.analyze(text=text, language=language)
    anonymized = AnonymizerEngine().anonymize(text=text, analyzer_results=findings)
    entities = tuple(sorted({finding.entity_type for finding in findings}))
    return RedactionResult(anonymized.text, entities)
