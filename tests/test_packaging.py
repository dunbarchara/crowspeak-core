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
