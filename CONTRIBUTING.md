# Contributing

Changes go through pull requests. Every pull request carries exactly one label from the release categories: breaking-change, new-feature, enhancement, bugfix, maintenance, documentation, dependencies.

## Setup

```bash
uv sync
uv run python -m scripts.check
```

`uv run python -m scripts.check` is the canonical gate. It stops at the first failure and runs exactly:

```text
ruff format --check .
ruff check .
mypy src tests scripts
python -m scripts.check_bruno_drift
python -m scripts.check_bundle_ledger
coverage run -m pytest
coverage report
uv build
uv audit --locked --preview-features audit-command
```

Coverage measures branches in `src/` and requires `fail_under = 98`. `uv audit` needs network access. `scripts.check_bundle_ledger` compares the contract ledger with the captured app bundle under `captures/`. Without that bundle it prints `skipped` and passes, so CI never runs the comparison.

## Adding an endpoint

Add all of the following:

- A frozen `Endpoint` row in `_endpoints.py` with the complete wire contract, including its api version.
- A typed `FarmadClient` method.
- A row in `tests/fixtures/farmad_app_contract.json` matching the wire path the app bundle uses.
- A fixture under `tests/fixtures/` with a real or redacted payload. Do not guess fixture shapes: capture one from the live API with `scripts/capture_data.py`, which writes every payload into `captures/`, and redact personal data before committing.
- A Bruno mirror in `.bruno/` whose docs name the client method it mirrors, satisfying `scripts/check_bruno_drift`.
- A conventional commit subject, which git-cliff renders into `CHANGELOG.md`.

## Changelog

`CHANGELOG.md` is generated with git-cliff from conventional commit subjects. Never edit it by hand. Features, bug fixes, documentation, and maintenance chores reach the changelog through their `feat:`, `fix:`, `docs:`, and `chore:` subjects. A subject with `!` after the type, such as `refactor!:`, lands under Breaking Changes. Other types without a `!` stay out of the changelog. Regenerate the whole file with `git-cliff --output CHANGELOG.md` and commit the result. At release, cut the dated section with `git-cliff --tag vX.Y.Z --output CHANGELOG.md`. A full regeneration keeps the version link definitions at the bottom of the file current, which `--prepend` does not.

## Captures and personal data

Captured payloads contain health data. Raw captures stay in `captures/`, which is git-ignored. Only redacted fixtures are committed. Synthetic names and identifiers for every person, every medication that is not a public product identifier, and every address.

## Test and repository rules

- Reuse `register_login_flow` from `tests/conftest.py` for login-flow tests.
- Pytest uses `asyncio_mode = auto`. Every warning is an error, including an unclosed session.
- Ruff uses `select = ["ALL"]` with the documented ignore list in `pyproject.toml`. mypy runs in strict mode.
- Do not add narrative code comments. Docstrings document the public API.
- Never log tokens, credentials, or OAuth state.
- Run the text-quality skills over all user-facing text before committing: README, commit subjects, docstrings, and error messages. No em dashes, no semicolon-joined clauses, no filler transitions.
- Do not mention AI, agents, or tooling in commit messages.
