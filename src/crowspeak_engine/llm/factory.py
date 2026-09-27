"""Select an LLMProvider from the LLM_PROVIDER environment variable."""

from __future__ import annotations

import os

from .azure_openai import AzureOpenAIProvider
from .base import LLMProvider
from .local import LocalOpenAIProvider

_PROVIDERS = {
    "azure": AzureOpenAIProvider.from_env,
    "local": LocalOpenAIProvider.from_env,
}


def provider_from_env() -> LLMProvider:
    """Build the provider named by LLM_PROVIDER ("azure" by default, or "local")."""
    name = os.environ.get("LLM_PROVIDER", "azure").strip().lower()
    try:
        build = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER {name!r}; expected one of: {', '.join(sorted(_PROVIDERS))}"
        ) from None
    return build()
