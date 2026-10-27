# Releasing crowspeak-engine

Releases are built and published by `.github/workflows/release.yml` using PyPI trusted
publishing (OIDC). No API token is stored in GitHub or anywhere else.

## One-time setup

Do these once, in this order. They need the project owner's accounts and cannot be done from
the repo.

1. **GitHub environments** (repo Settings > Environments): create `testpypi` and `pypi`. On
   `pypi`, add yourself as a required reviewer, so every real release waits for a human.
2. **TestPyPI** (test.pypi.org): sign in, then Account settings > Publishing > add a *pending*
   publisher for the project name `crowspeak-engine`:
   - Owner: `dunbarchara`, repository: `crowspeak-core`
   - Workflow: `release.yml`, environment: `testpypi`
3. **PyPI** (pypi.org): the same pending publisher, with environment `pypi`.

A pending publisher creates the project on first upload. Before step 2, check that the name
`crowspeak-engine` is free on both indexes.

## Cutting a release

1. Make your changes and bump the version in `src/crowspeak_engine/_version.py`. While the
   version is 0.x, a minor bump may break the public API (see "Public API and stability" in
   `engine-design.md`). Use a version that has never been uploaded to either index.
2. Open a PR with the changes and the bump. Merge it once CI (tests, mypy, build) passes.
3. The merge starts the workflow, because it changes `_version.py`. It builds, verifies the
   wheel contents, and publishes to TestPyPI. Check the project page, then install from it:

   ```
   uv run --no-project --index-url https://test.pypi.org/simple/      --extra-index-url https://pypi.org/simple/ --with crowspeak-engine==<version>      python -c "import crowspeak_engine; print(crowspeak_engine.__version__)"
   ```

4. The `publish-pypi` job then waits for approval. Approve the `pypi` deployment in the Actions
   run (Review deployments). The same artifacts that went to TestPyPI are uploaded to PyPI.
5. After the PyPI upload, the workflow creates the `v<version>` tag and a GitHub Release on the
   released commit. There is nothing to tag by hand.

A **manual run** of the workflow (Actions > Release > Run workflow) is a dry run: it builds and
publishes to TestPyPI only.

## Notes

- Index uploads are permanent. A version can never be replaced or reused, even after deleting
  it, so a mistake costs a new version number.
- Re-running for a version already on TestPyPI is safe: `--check-url` skips files that are
  already there.
- A merge releases only if `v<version>` does not exist yet, so touching `_version.py` without
  changing the number does nothing. Manual runs publish whatever `_version.py` says.
- Only one release runs at a time. A run waiting for approval holds the queue; a later merge
  waits behind it. An approval request expires after 30 days.
- The `pypi` environment must allow deployments from `main`, and "Prevent self-review" must be
  off, or you cannot approve your own release.
