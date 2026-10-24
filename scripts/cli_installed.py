"""Run the reference CLI against the installed crowspeak-engine package, not the repo source.

The CLI lives in src/ beside the engine and is not part of the wheel, so putting src/ on
sys.path would shadow the installed engine with the source one. This script instead builds a
throwaway venv, installs the engine into it, and loads src/crowspeak_cli by file path.

Usage (options before `--` are ours, everything after goes to the CLI):
    python scripts/cli_installed.py [--index testpypi|pypi] [--version X.Y.Z] [-- CLI ARGS]

With no --index, the engine is built from this checkout as a wheel.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_PACKAGE = ROOT / "src" / "crowspeak_cli"
TESTPYPI_INDEX = "https://test.pypi.org/simple/"
PYPI_INDEX = "https://pypi.org/simple/"

# Runs inside the venv. -I (isolated) keeps cwd and PYTHONPATH off sys.path, so the engine can
# only come from site-packages; the check below fails loudly if that ever stops being true.
BOOTSTRAP = """
import importlib.util
import sys
import sysconfig
from pathlib import Path

import crowspeak_engine

site = Path(sysconfig.get_paths()["purelib"]).resolve()
engine = Path(crowspeak_engine.__file__).resolve()
if site not in engine.parents:
    sys.exit(f"cli_installed: crowspeak_engine came from {engine}, not site-packages ({site})")

package = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location(
    "crowspeak_cli", package / "__init__.py", submodule_search_locations=[str(package)]
)
module = importlib.util.module_from_spec(spec)
sys.modules["crowspeak_cli"] = module
spec.loader.exec_module(module)

from crowspeak_cli.cli import main

sys.argv = ["crowspeak-cli", *sys.argv[2:]]
main()
"""


def run(cmd: list[str], **kwargs) -> None:
    subprocess.run(cmd, check=True, **kwargs)


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def main() -> int:
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    ours, cli_args = argv[:split], argv[split + 1 :]

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--index",
        choices=["testpypi", "pypi"],
        help="install the published package from this index instead of building a wheel",
    )
    parser.add_argument("--version", help="engine version to install (with --index)")
    args = parser.parse_args(ours)
    if args.version and not args.index:
        parser.error("--version needs --index")

    tmp = Path(tempfile.mkdtemp(prefix="crowspeak-cli-installed-"))
    try:
        venv = tmp / "venv"
        run(["uv", "venv", "--quiet", str(venv)])
        python = str(venv_python(venv))
        install = ["uv", "pip", "install", "--quiet", "--python", python]

        if args.index:
            spec = "crowspeak-engine" + (f"=={args.version}" if args.version else "")
            if args.index == "testpypi":
                # openai and friends are not on TestPyPI, so fall back to the real index.
                install += [
                    "--index-url", TESTPYPI_INDEX,
                    "--extra-index-url", PYPI_INDEX,
                    "--index-strategy", "unsafe-best-match",
                ]  # fmt: skip
            run([*install, spec, "python-dotenv"])
            print(f"cli_installed: engine from {args.index}", file=sys.stderr)
        else:
            run(["uv", "build", "--quiet", "--wheel", "--out-dir", str(tmp / "dist")], cwd=ROOT)
            (wheel,) = (tmp / "dist").glob("*.whl")
            run([*install, str(wheel), "python-dotenv"])
            print(f"cli_installed: engine from local wheel {wheel.name}", file=sys.stderr)

        # cwd stays at the repo root so the CLI finds .env the way it does in dev.
        result = subprocess.run(
            [python, "-I", "-c", BOOTSTRAP, str(CLI_PACKAGE), *cli_args], cwd=ROOT
        )
        return result.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
