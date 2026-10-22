"""Fail unless dist/ holds exactly the engine: one wheel and one sdist, with nothing else shipped.

Usage: python scripts/check_dist.py [dist_dir]
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

PACKAGE = "crowspeak_engine"
REQUIRED = {f"{PACKAGE}/__init__.py", f"{PACKAGE}/py.typed"}
# Source-tree dirs that must never reach a published artifact.
FORBIDDEN = ("crowspeak_cli", "crowspeak_tui")


def check_wheel(path: Path) -> list[str]:
    errors = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
    for name in names:
        top = name.split("/")[0]
        if top != PACKAGE and not top.endswith(".dist-info"):
            errors.append(f"{path.name}: unexpected top-level entry {name!r}")
    errors += [f"{path.name}: missing {r}" for r in sorted(REQUIRED - set(names))]
    for needed in ("LICENSE", "NOTICE"):
        if not any(n.endswith(f".dist-info/licenses/{needed}") for n in names):
            errors.append(f"{path.name}: missing license file {needed}")
    return errors


def check_sdist(path: Path) -> list[str]:
    with tarfile.open(path) as t:
        names = t.getnames()
    return [
        f"{path.name}: contains {name!r}"
        for name in names
        if any(f"/{bad}" in name for bad in FORBIDDEN)
    ]


def main() -> int:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
    errors = []
    if len(wheels) != 1 or len(sdists) != 1:
        errors.append(
            f"expected one wheel and one sdist in {dist}, found {len(wheels)}/{len(sdists)}"
        )
    for w in wheels:
        errors += check_wheel(w)
    for s in sdists:
        errors += check_sdist(s)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if not errors:
        print(f"ok: {wheels[0].name}, {sdists[0].name}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
