"""Expression tags in the NPC's streamed reply, e.g. ``[happy] Bonjour!``.

The NPC's LLM prefixes its text with bracketed labels from a closed vocabulary. This
parser strips them from the stream incrementally and reports them separately, so clients
and TTS adapters get clean text plus a typed expression signal.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)

EXPRESSIONS = ("neutral", "happy", "sad", "angry", "surprised", "thinking")
DEFAULT_EXPRESSION = "neutral"

# A '[' with no ']' within this many characters (brackets included) is literal text.
MAX_TAG_LEN = 20

_WORD = re.compile(r"[a-z_]+")


@dataclass(frozen=True)
class Expression:
    label: str


class ExpressionTagParser:
    """Incremental parser: call ``feed`` per stream delta, then ``finish`` at the end.

    Each call returns text strings and ``Expression`` markers in stream order. A tag may
    be split across deltas, so a trailing ``[...`` is held back until it resolves.
    """

    def __init__(self, labels: Iterable[str] = EXPRESSIONS) -> None:
        self._labels = frozenset(labels)
        self._pending: str | None = None  # buffered text starting at an open '['
        self._skip_ws = False  # swallow whitespace right after a removed tag

    def feed(self, delta: str) -> list[str | Expression]:
        out: list[str | Expression] = []
        for ch in delta:
            if self._pending is None:
                if ch == "[":
                    self._pending = "["
                else:
                    self._emit_text(out, ch)
                continue
            if ch == "[":  # the earlier '[' was literal; restart on this one
                self._emit_text(out, self._pending)
                self._pending = "["
                continue
            self._pending += ch
            if ch == "]":
                self._close(out)
            elif len(self._pending) >= MAX_TAG_LEN:
                self._emit_text(out, self._pending)
                self._pending = None
        return out

    def finish(self) -> list[str | Expression]:
        """Flush anything still buffered (an unclosed '[' is plain text)."""
        out: list[str | Expression] = []
        if self._pending is not None:
            self._emit_text(out, self._pending)
            self._pending = None
        return out

    def _close(self, out: list[str | Expression]) -> None:
        raw = self._pending or ""
        self._pending = None
        name = raw[1:-1].strip().lower()
        if name in self._labels:
            out.append(Expression(name))
            self._skip_ws = True
        elif _WORD.fullmatch(name):
            logger.warning("Dropping unknown expression tag %r", raw)
            self._skip_ws = True
        else:  # e.g. "[1]" or "[]": not a tag, keep as text
            self._emit_text(out, raw)

    def _emit_text(self, out: list[str | Expression], text: str) -> None:
        if self._skip_ws:
            text = text.lstrip()
            if not text:
                return
            self._skip_ws = False
        if out and isinstance(out[-1], str):
            out[-1] += text
        else:
            out.append(text)
