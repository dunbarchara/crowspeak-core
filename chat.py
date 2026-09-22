"""Minimal terminal chat loop against an Azure AI Foundry (Azure OpenAI) deployment."""

import os

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")

SYSTEM_PROMPT = "You are a helpful assistant."


def main() -> None:
    client = AzureOpenAI(azure_endpoint=ENDPOINT, api_key=API_KEY, api_version=API_VERSION)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("CrowSpeak chat (Azure Foundry). Type 'exit' or Ctrl+C to quit.\n")

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

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(model=DEPLOYMENT, messages=messages)
        except Exception as e:
            print(f"error: {e}\n")
            messages.pop()
            continue

        reply = response.choices[0].message.content
        print(f"assistant> {reply}\n")
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
