"""Value types for the corrections analyzer: feedback on a learner's own message."""

from __future__ import annotations

from dataclasses import dataclass

# Closed vocabularies, like EXPRESSIONS: the analyzer's JSON schema is built from these
# and anything else it returns is rejected.
CATEGORIES = ("grammar", "vocabulary", "spelling", "naturalness", "punctuation")
SEVERITIES = ("error", "suggestion")


@dataclass(frozen=True)
class CorrectionItem:
    original: str  # the quoted substring of the learner's message
    suggestion: str
    category: str
    severity: str
    explanation: str
    explanation_language: str
    # (start, end) character offsets into the message, computed by the engine from
    # `original`; None if the quote could not be located.
    span: tuple[int, int] | None = None
    confidence: float | None = None

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "suggestion": self.suggestion,
            "category": self.category,
            "severity": self.severity,
            "explanation": self.explanation,
            "explanation_language": self.explanation_language,
            "span": None if self.span is None else {"start": self.span[0], "end": self.span[1]},
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CorrectionItem:
        span = data.get("span")
        return cls(
            original=data["original"],
            suggestion=data["suggestion"],
            category=data["category"],
            severity=data["severity"],
            explanation=data["explanation"],
            explanation_language=data["explanation_language"],
            span=None if span is None else (span["start"], span["end"]),
            confidence=data.get("confidence"),
        )


@dataclass(frozen=True)
class Corrections:
    language: str  # the learner's target language code, e.g. "es-MX"
    original: str
    corrected: str
    is_correct: bool
    items: tuple[CorrectionItem, ...] = ()
    praise: str | None = None

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "original": self.original,
            "corrected": self.corrected,
            "is_correct": self.is_correct,
            "items": [i.to_dict() for i in self.items],
            "praise": self.praise,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Corrections:
        return cls(
            language=data["language"],
            original=data["original"],
            corrected=data["corrected"],
            is_correct=data["is_correct"],
            items=tuple(CorrectionItem.from_dict(i) for i in data.get("items", [])),
            praise=data.get("praise"),
        )
