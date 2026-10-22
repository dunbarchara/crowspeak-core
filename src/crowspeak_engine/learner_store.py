"""Loading and saving learners. The engine defines the protocol; real storage is the wrapper's."""

from __future__ import annotations

import copy
from typing import Protocol

from .session import Learner


class LearnerStore(Protocol):
    def load(self, learner_id: str) -> Learner | None:
        """The stored learner, or None if there is none with this id."""
        ...

    def save(self, learner: Learner) -> None:
        """Store `learner`, replacing any existing one with the same id."""
        ...


class InMemoryLearnerStore:
    """Keeps serialized learners, so it exercises the same round trip a real store would."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    def load(self, learner_id: str) -> Learner | None:
        data = self._data.get(learner_id)
        return None if data is None else Learner.from_dict(copy.deepcopy(data))

    def save(self, learner: Learner) -> None:
        self._data[learner.id] = learner.to_dict()
