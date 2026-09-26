"""Minimal terminal chat loop against an Azure AI Foundry (Azure OpenAI) deployment."""

import os
import sys

from dotenv import load_dotenv
from openai import AzureOpenAI

from proficiency import Proficiency
from session import Session

load_dotenv()

# Windows terminals default to a codepage (e.g. cp1252) that can't print
# Japanese or other non-Latin scripts; force UTF-8 so target-language output
# doesn't crash the loop.
sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")


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


def configure_session() -> Session:
    print("Let's set up your practice session.\n")
    native_language = _prompt("Your native language (ISO code)", "en")
    target_language = _prompt("Language to practice (ISO code)", "ja")
    proficiency = _prompt_proficiency()
    input_side = _prompt_choice("Type your messages in", ["native", "target"], "native")
    response_side = _prompt_choice("Assistant should respond in", ["native", "target"], "target")

    return Session.begin(
        native_language=native_language,
        target_language=target_language,
        proficiency=proficiency,
        user_input_language=native_language if input_side == "native" else target_language,
        llm_response_language=native_language if response_side == "native" else target_language,
    )


def main() -> None:
    client = AzureOpenAI(azure_endpoint=ENDPOINT, api_key=API_KEY, api_version=API_VERSION)
    session = configure_session()

    print("\nCrowSpeak chat (Azure Foundry). Type 'exit' or Ctrl+C to quit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        session.add_user_message(user_input)

        try:
            response = client.chat.completions.create(
                model=DEPLOYMENT, messages=session.to_api_messages()
            )
        except Exception as e:
            print(f"error: {e}\n")
            session.history.pop()
            continue

        reply = response.choices[0].message.content
        print(f"assistant> {reply}\n")
        session.add_assistant_message(reply)


if __name__ == "__main__":
    main()
