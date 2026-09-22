"""Per-language, per-CEFR-level instruction fragments for Session's system prompt.

Add support for a new target language by adding an entry to _ADAPTERS. Levels
left undefined for a language fall back to a generic, language-agnostic
description.
"""

from proficiency import Proficiency

_ADAPTERS: dict[str, dict[Proficiency, str]] = {
    "ja": {
        Proficiency.A1: (
            "Use only basic greetings, self-introductions, and simple です/ます "
            "sentence patterns. Write primarily in hiragana and katakana; limit "
            "kanji to a small set of very common characters (roughly JLPT N5) "
            "and keep sentences short, with no subordinate clauses."
        ),
        Proficiency.A2: (
            "Use simple present, past, and negative です/ます forms. Common "
            "kanji up to roughly JLPT N4 are fine alongside hiragana/katakana. "
            "Keep sentences short, avoid complex particle combinations, and "
            "stick to everyday topics like family, routines, and shopping."
        ),
        Proficiency.B1: (
            "Mix casual and polite forms naturally, as appropriate for a peer "
            "conversation. Everyday kanji up to roughly JLPT N3 are fine. "
            "Simple subordinate clauses are okay, but avoid formal keigo, "
            "literary phrasing, or bureaucratic vocabulary."
        ),
        Proficiency.B2: (
            "Use natural conversational Japanese with a broader range of "
            "grammar, including causative, passive, and conditional forms. "
            "Kanji use can extend to roughly JLPT N2. Light, contextually "
            "natural keigo (e.g. customer-service scenarios) is fine."
        ),
        Proficiency.C1: (
            "Use fluent, idiomatic Japanese with nuanced particle usage, "
            "varied sentence structures, and appropriate keigo register-"
            "switching. Kanji use can extend to roughly JLPT N1. Avoid only "
            "highly specialized or archaic vocabulary unless asked for."
        ),
        Proficiency.C2: (
            "Converse as a native speaker would: idiomatic expressions, "
            "regional or colloquial variation, and literary or technical "
            "vocabulary as context demands, with unrestricted kanji use."
        ),
    },
}

_GENERIC_FALLBACK: dict[Proficiency, str] = {
    Proficiency.A1: "Use only the most basic vocabulary and grammar. Keep sentences very short and simple.",
    Proficiency.A2: "Use simple, everyday vocabulary and basic sentence structures. Keep sentences short.",
    Proficiency.B1: "Use everyday vocabulary and moderately complex sentences, as in a casual conversation with a peer.",
    Proficiency.B2: "Use a broad vocabulary and varied grammar, as in a fluent, natural conversation.",
    Proficiency.C1: "Use fluent, idiomatic language with nuanced grammar and register.",
    Proficiency.C2: "Converse as a native speaker would, with no vocabulary or grammar restrictions.",
}


def get_adapter(target_language: str, proficiency: Proficiency) -> str:
    """Return the system-prompt instruction fragment for a language/level pair."""
    return _ADAPTERS.get(target_language, {}).get(proficiency, _GENERIC_FALLBACK[proficiency])
