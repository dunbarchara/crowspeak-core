"""The engine must stay UI-agnostic: no terminal I/O, no environment reads."""

import re
from pathlib import Path

import crowspeak_engine

ROOT = Path(crowspeak_engine.__file__).parent


def test_no_terminal_io_in_engine():
    for path in ROOT.rglob("*.py"):
        assert not re.search(r"\b(print|input)\(", path.read_text(encoding="utf-8")), path


def test_no_env_reads_outside_provider_adapters():
    for path in ROOT.rglob("*.py"):
        if path.parent.name == "llm":
            continue
        assert "os.environ" not in path.read_text(encoding="utf-8"), path
