"""The installed package's metadata agrees with the code."""

from importlib import metadata

import crowspeak_engine


def test_version_matches_installed_metadata():
    assert crowspeak_engine.__version__ == metadata.version("crowspeak-engine")


def test_py_typed_marker_is_present():
    from importlib import resources

    assert resources.files("crowspeak_engine").joinpath("py.typed").is_file()


def test_all_names_resolve():
    for name in crowspeak_engine.__all__:
        assert hasattr(crowspeak_engine, name), name


def test_provider_config_api_is_top_level():
    from crowspeak_engine import ProviderConfig, build_provider, providers_from_config

    provider = build_provider(ProviderConfig(kind="local"))
    assert providers_from_config(ProviderConfig(kind="local")).default is not None
    assert provider is not None


def test_env_helpers_and_adapters_live_in_llm_only():
    from crowspeak_engine import llm

    for name in ("AzureOpenAIProvider", "LocalOpenAIProvider", "providers_from_env"):
        assert name in llm.__all__
    assert not hasattr(crowspeak_engine, "providers_from_env")
