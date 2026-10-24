"""Keeps the CLI's learner in a JSON file next to the CLI, so setup survives between runs.

The file is plain, indented JSON on purpose: it is the CLI's test fixture, meant to be read and
edited by hand. The engine only defines the `LearnerStore` protocol; real storage is ours.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from crowspeak_engine import Learner

DEFAULT_PROFILE_PATH = Path(__file__).parent / "learner.json"


class ProfileFileError(Exception):
    """The profile file exists but cannot be used. The file is left as it was."""


class JsonFileLearnerStore:
    """One learner in one file. Satisfies the engine's `LearnerStore` protocol."""

    def __init__(self, path: Path | str = DEFAULT_PROFILE_PATH) -> None:
        self.path = Path(path)

    def load_current(self) -> Learner | None:
        """The stored learner, or None if there is no file yet."""
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as e:
            raise ProfileFileError(f"{self.path}: cannot read the profile ({e})") from e
        try:
            return Learner.from_dict(json.loads(text))
        except (KeyError, ValueError, TypeError) as e:
            # ValueError covers bad JSON, bad field values and an unsupported schema_version.
            detail = e.args[0] if isinstance(e, KeyError) and e.args else e
            raise ProfileFileError(
                f"{self.path}: not a valid profile ({type(e).__name__}: {detail}). "
                "Fix or delete the file, or run with --reset to replace it."
            ) from e

    def load(self, learner_id: str) -> Learner | None:
        learner = self.load_current()
        return learner if learner is not None and learner.id == learner_id else None

    def save(self, learner: Learner) -> None:
        """Write the learner atomically: a crash cannot leave a half-written profile."""
        text = json.dumps(learner.to_dict(), indent=2, sort_keys=True, ensure_ascii=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text + "\n")
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
