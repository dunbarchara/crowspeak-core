"""Minimal terminal client for the CrowSpeak engine."""

import argparse
import asyncio
import os
import sys
from collections.abc import Callable
from pathlib import Path

import crowspeak_engine
from crowspeak_cli import render
from crowspeak_cli.store import DEFAULT_PROFILE_PATH, JsonFileLearnerStore, ProfileFileError
from crowspeak_engine import (
    AnalyzerError,
    CorrectionsReady,
    Engine,
    EngineError,
    Features,
    InteractionPrefs,
    LanguageProfile,
    Learner,
    Message,
    Npc,
    Proficiency,
    Target,
    TranscriptDelta,
    TurnCompleted,
)
from crowspeak_engine.llm import JOB_CORRECTIONS, JOB_NPC, Providers, providers_from_env


def _load_env() -> None:
    """Load `.env` into the environment (the engine never does). Needs the `cli` dependency group."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "crowspeak-cli: python-dotenv is not installed. "
            "Install the CLI dependencies: uv sync --group cli",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    load_dotenv()


def _describe(provider: object) -> str:
    describe = getattr(provider, "describe", None)
    return describe() if callable(describe) else repr(provider)


def _provider_lines(providers: Providers, corrections: bool) -> list[str]:
    """What serves each built-in job: the default, or the job's own provider."""
    lines = [f"default: {_describe(providers.default)}"]
    for job in (JOB_NPC, JOB_CORRECTIONS):
        own = providers.jobs.get(job)
        text = _describe(own) if own is not None else "(default)"
        if job == JOB_CORRECTIONS and not corrections:
            text += " (unused: --corrections is off)"
        lines.append(f"{job}: {text}")
    return lines


def _debug_env() -> str:
    """The provider-selecting variables as the process sees them (shell beats .env)."""
    names = sorted(
        n
        for n in os.environ
        if n == "LLM_PROVIDER" or n.startswith(("LLM_NPC_", "LLM_CORRECTIONS_"))
    )
    # Secrets are reported as set or not, never printed.
    shown = ((n, "(set)" if n.endswith("_API_KEY") else os.environ[n]) for n in names)
    return " ".join(f"{n}={v}" for n, v in shown) or "(none set; defaults apply)"


def _prompt(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def _prompt_choice(label: str, options: list[str], default: str) -> str:
    while True:
        value = input(f"{label} ({'/'.join(options)}) [{default}]: ").strip().lower()
        if not value:
            return default
        if value in options:
            return value
        print(f"Please enter one of: {', '.join(options)}")


def _prompt_proficiency(default: Proficiency = Proficiency.A1) -> Proficiency:
    levels = [p.value for p in Proficiency]
    while True:
        value = input(f"Proficiency ({'/'.join(levels)}) [{default.value}]: ").strip().upper()
        if not value:
            return default
        try:
            return Proficiency(value)
        except ValueError:
            print(f"Please enter one of: {', '.join(levels)}")


def configure_learner() -> Learner:
    print("Let's set up your practice session.\n")
    while True:
        native = _prompt("Your native language (ISO code)", "en")
        target = _prompt("Language to practice (ISO code)", "ja")
        if native != target:
            break
        print("Native and target language must differ.")
    proficiency = _prompt_proficiency()
    input_side = _prompt_choice("Type your messages in", ["native", "target"], "native")
    response_side = _prompt_choice("Assistant should respond in", ["native", "target"], "target")

    # The choices are the learner's defaults, so they are saved with the profile.
    prefs = InteractionPrefs(
        learner_input_language=native if input_side == "native" else target,
        npc_response_language=native if response_side == "native" else target,
    )
    return Learner(LanguageProfile(native=native, target=Target(target, proficiency)), prefs=prefs)


def load_or_configure(
    store: JsonFileLearnerStore,
    reset: bool = False,
    configure: Callable[[], Learner] = configure_learner,
) -> tuple[Learner, bool]:
    """The saved learner, or a freshly configured one that is saved. True if it was loaded.

    `reset` skips loading, so it also recovers from an unreadable file. Setup finishes
    before the old file is replaced, so abandoning it (Ctrl+C) keeps the old profile.
    """
    if not reset:
        learner = store.load_current()
        if learner is not None:
            return learner, True
    learner = configure()
    store.save(learner)
    return learner, False


def _load_persona(value: str | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else value


def _use_color(stream) -> bool:
    """Color only for a real terminal, and never when NO_COLOR is set (no-color.org)."""
    return stream.isatty() and not os.environ.get("NO_COLOR")


def _review(history: list[Message], arg: str, color: bool, more: bool = False) -> str:
    """Corrections for the learner's last message, or the Nth (1-based) with `/review N`.
    With `more`, the folded ones (`/review-more`): minor fixes and anything over the cap."""
    learner_messages = [m for m in history if m.role == "user"]
    if not learner_messages:
        return "Nothing to review yet."
    if arg:
        try:
            index = int(arg)
        except ValueError:
            return f"Usage: {'/review-more' if more else '/review'} [N]"
        if not 1 <= index <= len(learner_messages):
            return f"No message {index}; you have written {len(learner_messages)}."
    else:
        index = len(learner_messages)
    message = learner_messages[index - 1]
    if message.corrections is None:
        return (
            f"Message {index} was not analyzed "
            "(corrections need --corrections and a message in your target language)."
        )
    if more:
        return render.format_more(message.corrections, color)
    out = render.format_corrections(message.corrections, color)
    hint = render.format_more_hint(message.corrections, index, color)
    return f"{out}\n{hint}" if hint else out


async def _chat(
    engine: Engine,
    learner: Learner,
    persona: str | None,
    corrections: bool,
    color: bool,
) -> None:
    features = Features(corrections=True) if corrections else None
    session = engine.start_session(learner, features=features)
    conversation = session.converse(
        Npc.default(native_language=learner.target.language, persona=persona)
    )
    name = conversation.npc.name.lower()

    print("\nCrowSpeak chat. Type 'exit' or Ctrl+C to quit.")
    if corrections:
        if conversation.resolve()[0] != learner.target.language:
            print(
                f"Note: corrections only run when you write in {learner.target.language}; "
                "none will appear with these settings."
            )
        print("Corrections are on: a one-line summary follows each reply.")
        print("Type /review [N] for the details of your last (or Nth) message,")
        print("and /review-more [N] for the minor fixes (accents, punctuation) folded out of it.")
    print()

    while True:
        try:
            user_input = (await asyncio.to_thread(input, "you> ")).strip()
        except EOFError:
            print("\nbye")
            return

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            return
        command, _, arg = user_input.partition(" ")
        if command.lower() in ("/review", "/review-more"):
            more = command.lower() == "/review-more"
            print(_review(conversation.history, arg.strip(), color, more), "\n")
            continue

        line_open = False  # True while the NPC's reply is mid-line
        async for event in conversation.send_text(user_input):
            if isinstance(event, TranscriptDelta):
                if not line_open:
                    print(f"{name}> ", end="")
                    line_open = True
                print(event.text, end="", flush=True)
            elif isinstance(event, TurnCompleted):
                print()  # end the reply; corrections, if any, follow
                line_open = False
            elif isinstance(event, CorrectionsReady):
                # Quiet by default: one line, with the message number to pass to /review.
                learner_ids = [m.id for m in conversation.history if m.role == "user"]
                number = (
                    learner_ids.index(event.message_id) + 1
                    if event.message_id in learner_ids
                    else None
                )
                print(render.format_summary(event.corrections, number, color))
            elif isinstance(event, AnalyzerError):
                print(render.format_analyzer_error(event, color))
            elif isinstance(event, EngineError):
                if line_open:
                    print()
                print(f"error: {event.message}")
                line_open = False
        print()


def main() -> None:
    parser = argparse.ArgumentParser(prog="crowspeak-cli")
    parser.add_argument(
        "--persona", help="Persona text, or path to a file containing it (default: generic partner)"
    )
    parser.add_argument(
        "--corrections",
        action="store_true",
        help="Show feedback on your messages after each reply (needs a JSON-capable LLM)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print which LLM provider/model serves each job"
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help="Where the learner profile is saved (default: learner.json next to the CLI)",
    )
    parser.add_argument(
        "--reset", action="store_true", help="Run setup again and replace the saved profile"
    )
    args = parser.parse_args()

    _load_env()
    # Windows terminals default to a codepage (e.g. cp1252) that can't print
    # Japanese or other non-Latin scripts; force UTF-8 so target-language output
    # doesn't crash the loop.
    sys.stdout.reconfigure(encoding="utf-8")

    persona = _load_persona(args.persona)
    try:
        providers = providers_from_env()
    except ValueError as e:  # unknown provider kind, or missing Azure variables
        print(f"crowspeak-cli: {e}", file=sys.stderr)
        raise SystemExit(1) from None
    if args.debug:
        # Which engine this run uses: site-packages (installed) or src/ (dev).
        print(
            f"[debug] engine: {crowspeak_engine.__version__} at {crowspeak_engine.__file__}",
            file=sys.stderr,
        )
        # .env does not override variables already set in the shell.
        print(f"[debug] env: {_debug_env()}", file=sys.stderr)
        for line in _provider_lines(providers, args.corrections):
            print(f"[debug] {line}", file=sys.stderr)
    engine = Engine(providers=providers)
    store = JsonFileLearnerStore(args.profile)
    try:
        learner, loaded = load_or_configure(store, args.reset)
    except ProfileFileError as e:
        print(f"crowspeak-cli: {e}", file=sys.stderr)
        raise SystemExit(1) from None
    if loaded:
        target = learner.target
        print(
            f"Loaded profile from {store.path}: "
            f"{learner.language.native} -> {target.language} ({target.proficiency.value}). "
            "Use --reset to change it."
        )
    else:
        print(f"Saved profile to {store.path}")
    try:
        asyncio.run(_chat(engine, learner, persona, args.corrections, _use_color(sys.stdout)))
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
