"""Build providers from explicit config, or from the environment.

`ProviderConfig`, `build_provider` and `providers_from_config` never touch the environment:
a wrapper app passes its configuration in. `providers_from_env` and `provider_from_env` map
`LLM_*` variables onto the same configs, as a convenience for the CLI, tests and local
development. This module is the only code in the engine that reads `os.environ`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .azure_openai import AzureOpenAIProvider
from .base import LLMProvider
from .local import LocalOpenAIProvider
from .providers import JOB_CORRECTIONS, JOB_NPC, Providers

_KINDS = ("azure", "local")

# The environment variable behind each required azure field, for error messages.
_AZURE_ENV = {
    "endpoint": "AZURE_OPENAI_ENDPOINT",
    "api_key": "AZURE_OPENAI_API_KEY",
    "model": "AZURE_OPENAI_DEPLOYMENT",
}


@dataclass(frozen=True)
class ProviderConfig:
    """Everything needed to build one provider. `endpoint` is the Azure endpoint or the
    local server's base URL; `model` is the Azure deployment or the local model tag."""

    kind: str  # "azure" or "local"
    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = field(default=None, repr=False)  # keep secrets out of logs
    api_version: str | None = None  # azure only


def build_provider(config: ProviderConfig) -> LLMProvider:
    """Build the provider `config` describes. Reads no environment variables."""
    kind = config.kind.strip().lower()
    if kind == "azure":
        if not (config.endpoint and config.api_key and config.model):
            missing = [f for f in _AZURE_ENV if not getattr(config, f)]
            raise ValueError(f"azure provider config is missing: {', '.join(missing)}")
        extra = {"api_version": config.api_version} if config.api_version else {}
        return AzureOpenAIProvider(
            endpoint=config.endpoint,
            api_key=config.api_key,
            deployment=config.model,
            **extra,
        )
    if kind == "local":
        given = {
            "base_url": config.endpoint,
            "model": config.model,
            "api_key": config.api_key,
        }
        return LocalOpenAIProvider(**{k: v for k, v in given.items() if v})
    raise ValueError(
        f"Unknown provider kind {config.kind!r}; expected one of: {', '.join(sorted(_KINDS))}"
    )


def providers_from_config(
    default: ProviderConfig, jobs: Mapping[str, ProviderConfig] | None = None
) -> Providers:
    """Build a `Providers` registry: `default` serves every job not listed in `jobs`."""
    return Providers(
        default=build_provider(default),
        jobs={name: build_provider(config) for name, config in (jobs or {}).items()},
    )


# --- environment mapping -----------------------------------------------------------


def _env(name: str) -> str | None:
    """The variable's value, or None if unset or blank (`.env` files often have `X=`)."""
    return os.environ.get(name, "").strip() or None


def _kind(var: str) -> str | None:
    """The provider kind named by `var` (lower-cased), or None if it isn't set."""
    kind = _env(var)
    if kind is None:
        return None
    kind = kind.lower()
    if kind not in _KINDS:
        raise ValueError(f"Unknown {var} {kind!r}; expected one of: {', '.join(sorted(_KINDS))}")
    return kind


def _default_kind() -> str:
    return _kind("LLM_PROVIDER") or "azure"


def _config_from_env(kind: str, model: str | None = None) -> ProviderConfig:
    """Read `kind`'s provider-level variables. A given `model` replaces the model variable."""
    if kind == "azure":
        config = ProviderConfig(
            kind="azure",
            model=model or _env("AZURE_OPENAI_DEPLOYMENT"),
            endpoint=_env("AZURE_OPENAI_ENDPOINT"),
            api_key=_env("AZURE_OPENAI_API_KEY"),
            api_version=_env("AZURE_OPENAI_API_VERSION"),
        )
        missing = [var for field_, var in _AZURE_ENV.items() if not getattr(config, field_)]
        if missing:
            raise ValueError(f"azure provider needs environment variables: {', '.join(missing)}")
        return config
    return ProviderConfig(
        kind="local",
        model=model or _env("LOCAL_LLM_MODEL"),
        endpoint=_env("LOCAL_LLM_BASE_URL"),
    )


def provider_from_env() -> LLMProvider:
    """Build the single provider named by LLM_PROVIDER ("azure" by default, or "local")."""
    return build_provider(_config_from_env(_default_kind()))


def providers_from_env(jobs: Iterable[str] = (JOB_NPC, JOB_CORRECTIONS)) -> Providers:
    """Build a `Providers` from the environment.

    `LLM_PROVIDER` selects the default. For each job name in `jobs`, `LLM_<JOB>_PROVIDER`
    and `LLM_<JOB>_MODEL` (job upper-cased, other characters replaced by `_`) assign it its
    own provider kind and/or model; a job with neither falls back to the default. Jobs are
    named by the caller rather than discovered, so pass any consumer-defined ones. Endpoint
    and key stay provider-level (`AZURE_OPENAI_*`, `LOCAL_LLM_*`) and shared; give a job its
    own account with `providers_from_config`.
    """
    default_kind = _default_kind()
    configs: dict[str, ProviderConfig] = {}
    for job in jobs:
        prefix = "LLM_" + re.sub(r"[^0-9A-Za-z]", "_", job).upper()
        kind = _kind(f"{prefix}_PROVIDER")
        model = _env(f"{prefix}_MODEL")
        if kind is None and model is None:
            continue
        configs[job] = _config_from_env(kind or default_kind, model)
    return providers_from_config(_config_from_env(default_kind), configs)
