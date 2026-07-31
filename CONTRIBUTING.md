# Contributing

Thanks for considering a contribution to `ins`. This guide covers setting up a
development environment, running tests, and the expectations for a pull
request.

## Development setup

Requires Python 3.11+.

```bash
git clone https://github.com/savai15/ins && cd ins
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Running tests

```bash
pytest -q            # full suite
pytest -q -k apt     # tests matching "apt"
```

The suite never touches a real system: every subprocess call is routed
through a fake runner (`tests/conftest.py`) that replays real captured
package-manager output from `tests/output_samples.py`. Parsing code is
therefore verified against authentic tool formats, but nothing is executed.

To try the CLI end-to-end without touching your system:

```bash
INS_FAKE=1 ins -s vlc
```

## Adding or changing a source adapter

1. Implement `SourceAdapter` in `ins/adapters/` (see `base.py` for the
   interface; `fake_adapter.py` is the reference implementation).
2. Capture realistic output of the tool you wrap (run it on a real system,
   or find canonical examples) and add it to `tests/output_samples.py`.
3. Add a `tests/test_<name>_adapter.py` mirroring the existing adapter tests.
4. Register the adapter in `ins/adapters/registry.py`.

## Code style

- Follow the existing style; keep lines under ~100 characters.
- No comments unless they explain non-obvious intent.
- Type hints on all public functions.
- Every user-facing change ships with tests.

## Pull request process

1. Base your branch on `main`; keep changes focused on one concern.
2. Run `pytest -q` and confirm the full suite is green.
3. Update the README if user-facing behavior changed, and add a `CHANGELOG.md`
   entry under `[Unreleased]`.
4. Open the PR with a short description of the change and its motivation.

## Releasing (maintainers)

1. Bump the version in `ins/__init__.py` and `pyproject.toml`.
2. Move `CHANGELOG.md` entries from `[Unreleased]` to the new version.
3. Tag and push, then create a release:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
gh release create vX.Y.Z --title "ins vX.Y.Z" --generate-notes
```
