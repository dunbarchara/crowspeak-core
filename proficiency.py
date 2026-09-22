"""CEFR proficiency levels used to scale LLM output within a Session."""

from enum import Enum


class Proficiency(Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
