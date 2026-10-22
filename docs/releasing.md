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

1. Pick the version and edit `src/crowspeak_engine/_version.py`. While the version is 0.x, a
   minor bump may break the public API (see "Public API and stability" in `engine-design.md`).
2. Merge to `main` and wait for CI (tests, mypy, build) to pass.
3. Tag that commit and push the tag. The tag must be `v` plus the version exactly:

   ```
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. The workflow builds, checks the tag against `_version.py`, verifies the wheel contents, and
   publishes to TestPyPI. Check the project page, then install from it:

   ```
   uv run --no-project --index-url https://test.pypi.org/simple/ \
     --extra-index-url https://pypi.org/simple/ --with crowspeak-engine==0.1.0 \
     python -c "import crowspeak_engine; print(crowspeak_engine.__version__)"
   ```

5. Approve the `pypi` environment deployment in the Actions run. The same artifacts that went
   to TestPyPI are then uploaded to PyPI.

A **manual run** of the workflow (Actions > Release > Run workflow) is a dry run: it builds and
publishes to TestPyPI only.

## Notes

- Index uploads are permanent. A version can never be replaced or reused, even after deleting
  it, so a mistake costs a new version number.
- Re-running for a version already on TestPyPI is safe: `--check-url` skips files that are
  already there.
- The tag check runs only for tag pushes. Manual runs publish whatever `_version.py` says.
