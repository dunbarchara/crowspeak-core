"""Declarative provider config (no environment) and its env mapping. No network: building
an adapter only constructs an HTTP client."""

import os
from dataclasses import replace

import pytest

from crowspeak_engine.llm import (
    JOB_CORRECTIONS,
    JOB_NPC,
    ProviderConfig,
    Providers,
    build_provider,
    providers_from_config,
    providers_from_env,
)
from crowspeak_engine.llm.azure_openai import AzureOpenAIProvider
from crowspeak_engine.llm.local import DEFAULT_MODEL, LocalOpenAIProvider

AZURE = ProviderConfig(
    kind="azure", endpoint="https://x.openai.azure.com/", api_key="sekrit", model="big"
)


@pytest.fixture
def clean_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("LLM_", "AZURE_OPENAI_", "LOCAL_LLM_")):
            monkeypatch.delenv(name)
    return monkeypatch


# --- config path: no environment involved -----------------------------------------


def test_build_azure_from_config():
    provider = build_provider(replace(AZURE, api_version="2025-01-01"))

    assert isinstance(provider, AzureOpenAIProvider)
    assert provider._deployment == "big"
    assert "x.openai.azure.com" in provider.describe()


def test_build_local_from_config_uses_defaults_for_unset_fields():
    provider = build_provider(ProviderConfig(kind="Local"))

    assert isinstance(provider, LocalOpenAIProvider)
    assert provider._model == DEFAULT_MODEL

    custom = build_provider(ProviderConfig(kind="local", model="qwen", endpoint="http://h:1/v1"))
    assert custom._model == "qwen"
    assert str(custom._client.base_url).rstrip("/") == "http://h:1/v1"


def test_azure_config_names_every_missing_field():
    with pytest.raises(ValueError, match="endpoint, api_key, model"):
        build_provider(ProviderConfig(kind="azure"))


def test_unknown_kind_lists_valid_kinds():
    with pytest.raises(ValueError, match="azure, local"):
        build_provider(ProviderConfig(kind="bogus"))


def test_api_key_is_not_in_repr():
    assert "sekrit" not in repr(AZURE)


def test_providers_from_config_builds_default_and_jobs():
    providers = providers_from_config(
        ProviderConfig(kind="local", model="small"),
        {JOB_CORRECTIONS: replace(AZURE, model="large"), "daily_tasks": AZURE},
    )

    assert isinstance(providers, Providers)
    assert providers.default._model == "small"
    assert providers.for_job(JOB_CORRECTIONS, "json")._deployment == "large"
    assert providers.for_job("daily_tasks", "json") is not providers.for_job(JOB_CORRECTIONS)
    assert providers.for_job(JOB_NPC) is providers.default


# --- env mapping ------------------------------------------------------------------


def test_env_without_job_vars_assigns_no_jobs(clean_env):
    clean_env.setenv("LLM_PROVIDER", "local")

    providers = providers_from_env()

    assert dict(providers.jobs) == {}
    assert isinstance(providers.default, LocalOpenAIProvider)


def test_local_npc_with_azure_corrections(clean_env):
    clean_env.setenv("LLM_PROVIDER", "local")
    clean_env.setenv("LLM_CORRECTIONS_PROVIDER", "azure")
    clean_env.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    clean_env.setenv("AZURE_OPENAI_API_KEY", "k")
    clean_env.setenv("AZURE_OPENAI_DEPLOYMENT", "d")

    providers = providers_from_env()

    assert isinstance(providers.for_job(JOB_NPC), LocalOpenAIProvider)
    corrections = providers.for_job(JOB_CORRECTIONS, "json")
    assert isinstance(corrections, AzureOpenAIProvider)
    assert corrections._deployment == "d"


def test_model_only_override_keeps_the_default_kind(clean_env):
    clean_env.setenv("LLM_PROVIDER", "local")
    clean_env.setenv("LOCAL_LLM_MODEL", "small")
    clean_env.setenv("LLM_CORRECTIONS_MODEL", "big")

    providers = providers_from_env()

    assert providers.default._model == "small"
    assert providers.for_job(JOB_CORRECTIONS)._model == "big"
    assert providers.for_job(JOB_NPC) is providers.default


def test_azure_model_override_does_not_need_the_deployment_variable(clean_env):
    clean_env.setenv("LLM_PROVIDER", "local")
    clean_env.setenv("LLM_CORRECTIONS_PROVIDER", "azure")
    clean_env.setenv("LLM_CORRECTIONS_MODEL", "gpt-x")
    clean_env.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    clean_env.setenv("AZURE_OPENAI_API_KEY", "k")

    providers = providers_from_env()

    assert providers.for_job(JOB_CORRECTIONS)._deployment == "gpt-x"


def test_a_job_can_target_a_different_azure_resource(clean_env):
    clean_env.setenv("LLM_PROVIDER", "azure")
    clean_env.setenv("AZURE_OPENAI_ENDPOINT", "https://east.openai.azure.com/")
    clean_env.setenv("AZURE_OPENAI_API_KEY", "key-east")
    clean_env.setenv("AZURE_OPENAI_DEPLOYMENT", "mini")
    clean_env.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    clean_env.setenv("LLM_CORRECTIONS_ENDPOINT", "https://west.services.ai.azure.com/")
    clean_env.setenv("LLM_CORRECTIONS_API_KEY", "key-west")
    clean_env.setenv("LLM_CORRECTIONS_MODEL", "big")
    clean_env.setenv("LLM_CORRECTIONS_API_VERSION", "2025-03-01-preview")

    providers = providers_from_env()

    default = providers.default
    corrections = providers.for_job(JOB_CORRECTIONS, "json")
    assert isinstance(corrections, AzureOpenAIProvider)  # kind inherited from LLM_PROVIDER
    assert (default._endpoint, default._deployment) == ("https://east.openai.azure.com/", "mini")
    assert default._client.api_key == "key-east"
    assert default._client._api_version == "2024-12-01-preview"
    assert (corrections._endpoint, corrections._deployment) == (
        "https://west.services.ai.azure.com/",
        "big",
    )
    assert corrections._client.api_key == "key-west"
    assert corrections._client._api_version == "2025-03-01-preview"


def test_job_overrides_apply_field_by_field(clean_env):
    clean_env.setenv("LLM_PROVIDER", "azure")
    clean_env.setenv("AZURE_OPENAI_ENDPOINT", "https://east.openai.azure.com/")
    clean_env.setenv("AZURE_OPENAI_API_KEY", "key-east")
    clean_env.setenv("AZURE_OPENAI_DEPLOYMENT", "mini")
    clean_env.setenv("LLM_NPC_API_KEY", "key-npc")  # only the key differs

    npc = providers_from_env().for_job(JOB_NPC)

    assert npc._client.api_key == "key-npc"
    assert npc._endpoint == "https://east.openai.azure.com/"  # inherited
    assert npc._deployment == "mini"  # inherited


def test_local_job_can_target_another_server(clean_env):
    clean_env.setenv("LLM_PROVIDER", "azure")
    clean_env.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    clean_env.setenv("AZURE_OPENAI_API_KEY", "k")
    clean_env.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    clean_env.setenv("LLM_NPC_PROVIDER", "local")
    clean_env.setenv("LLM_NPC_ENDPOINT", "http://gpu-box:11434/v1")
    clean_env.setenv("LLM_NPC_MODEL", "gemma")

    npc = providers_from_env().for_job(JOB_NPC)

    assert isinstance(npc, LocalOpenAIProvider)
    assert npc._model == "gemma"
    assert str(npc._client.base_url).rstrip("/") == "http://gpu-box:11434/v1"


def test_job_names_are_normalised_and_only_listed_jobs_are_read(clean_env):
    clean_env.setenv("LLM_PROVIDER", "local")
    clean_env.setenv("LLM_DAILY_TASKS_MODEL", "tasks-model")
    clean_env.setenv("LLM_UNLISTED_MODEL", "ignored")

    providers = providers_from_env(jobs=("daily-tasks",))

    assert set(providers.jobs) == {"daily-tasks"}
    assert providers.for_job("daily-tasks")._model == "tasks-model"


def test_unknown_job_provider_names_the_variable(clean_env):
    clean_env.setenv("LLM_PROVIDER", "local")
    clean_env.setenv("LLM_CORRECTIONS_PROVIDER", "bogus")

    with pytest.raises(ValueError, match="LLM_CORRECTIONS_PROVIDER.*azure, local"):
        providers_from_env()


def test_missing_azure_variables_are_named(clean_env):
    clean_env.setenv("LLM_PROVIDER", "azure")

    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT.*AZURE_OPENAI_API_KEY"):
        providers_from_env()


def test_blank_values_count_as_unset(clean_env):
    clean_env.setenv("LLM_PROVIDER", "")
    clean_env.setenv("LLM_CORRECTIONS_PROVIDER", "  ")
    clean_env.setenv("LLM_CORRECTIONS_MODEL", "")
    clean_env.setenv("AZURE_OPENAI_ENDPOINT", "https://x.openai.azure.com/")
    clean_env.setenv("AZURE_OPENAI_API_KEY", "k")
    clean_env.setenv("AZURE_OPENAI_DEPLOYMENT", "d")

    providers = providers_from_env()

    assert isinstance(providers.default, AzureOpenAIProvider)  # blank LLM_PROVIDER: the default
    assert dict(providers.jobs) == {}
