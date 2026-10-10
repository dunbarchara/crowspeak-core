"""Minimal terminal client for the CrowSpeak engine."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from crowspeak_cli import render
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
    TranscriptDelta,
    TurnCompleted,
)
from crowspeak_engine.llm import provider_from_env


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


def configure_learner() -> tuple[Learner, InteractionPrefs]:
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

    learner = Learner(LanguageProfile(native=native, target=target, proficiency=proficiency))
    prefs = InteractionPrefs(
        learner_input_language=native if input_side == "native" else target,
        npc_response_language=native if response_side == "native" else target,
    )
    return learner, prefs


def _load_persona(value: str | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else value


def _use_color(stream) -> bool:
    """Color only for a real terminal, and never when NO_COLOR is set (no-color.org)."""
    return stream.isatty() and not os.environ.get("NO_COLOR")


def _review(history: list[Message], arg: str, color: bool) -> str:
    """Corrections for the learner's last message, or the Nth (1-based) with `/review N`."""
    learner_messages = [m for m in history if m.role == "user"]
    if not learner_messages:
        return "Nothing to review yet."
    if arg:
        try:
            index = int(arg)
        except ValueError:
            return "Usage: /review [N]"
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
    return render.format_corrections(message.corrections, color)


async def _chat(
    engine: Engine,
    learner: Learner,
    prefs: InteractionPrefs,
    persona: str | None,
    corrections: bool,
    color: bool,
) -> None:
    features = Features(corrections=True) if corrections else None
    session = engine.start_session(learner, prefs, features)
    conversation = session.converse(
        Npc.default(native_language=learner.language.target, persona=persona)
    )
    name = conversation.npc.name.lower()

    print("\nCrowSpeak chat. Type 'exit' or Ctrl+C to quit.")
    if corrections:
        if conversation.resolve()[0] != learner.language.target:
            print(
                f"Note: corrections only run when you write in {learner.language.target}; "
                "none will appear with these settings."
            )
        print("Corrections are on: a one-line summary follows each reply.")
        print("Type /review [N] for the details of your last (or Nth) message.")
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
        if command.lower() == "/review":
            print(_review(conversation.history, arg.strip(), color), "\n")
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
        "--debug", action="store_true", help="Print which LLM provider/model is in use"
    )
    args = parser.parse_args()

    load_dotenv()
    # Windows terminals default to a codepage (e.g. cp1252) that can't print
    # Japanese or other non-Latin scripts; force UTF-8 so target-language output
    # doesn't crash the loop.
    sys.stdout.reconfigure(encoding="utf-8")

    persona = _load_persona(args.persona)
    llm = provider_from_env()
    if args.debug:
        # load_dotenv() does not override variables already set in the shell.
        print(f"[debug] LLM_PROVIDER={os.environ.get('LLM_PROVIDER', 'azure')}", file=sys.stderr)
        print(f"[debug] {getattr(llm, 'describe', lambda: repr(llm))()}", file=sys.stderr)
    engine = Engine(llm)
    learner, prefs = configure_learner()
    try:
        asyncio.run(
            _chat(engine, learner, prefs, persona, args.corrections, _use_color(sys.stdout))
        )
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
