"""Minimal terminal client for the CrowSpeak engine."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from crowspeak_engine import (
    Engine,
    EngineError,
    InteractionPrefs,
    LanguageProfile,
    Learner,
    Npc,
    Proficiency,
    TranscriptDelta,
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


async def _chat(engine: Engine, learner: Learner, prefs: InteractionPrefs, persona: str | None) -> None:
    session = engine.start_session(learner, prefs)
    conversation = session.converse(
        Npc.default(native_language=learner.language.target, persona=persona)
    )
    name = conversation.npc.name.lower()

    print("\nCrowSpeak chat. Type 'exit' or Ctrl+C to quit.\n")

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

        started = False
        async for event in conversation.send_text(user_input):
            if isinstance(event, TranscriptDelta):
                if not started:
                    print(f"{name}> ", end="")
                    started = True
                print(event.text, end="", flush=True)
            elif isinstance(event, EngineError):
                print(f"error: {event.message}")
        print("\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="crowspeak-cli")
    parser.add_argument(
        "--persona", help="Persona text, or path to a file containing it (default: generic partner)"
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
        asyncio.run(_chat(engine, learner, prefs, persona))
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
