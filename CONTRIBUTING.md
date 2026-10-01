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
coverage run -m pytest
coverage report
pip-audit
```

Coverage measures branches in `src/` and requires `fail_under = 98`. `pip-audit` needs network access.

## Adding an endpoint

Add all of the following:

- A frozen `Endpoint` row in `_endpoints.py` with the complete wire contract, including its api version.
- A typed `FarmadClient` method.
- A row in `tests/fixtures/farmad_app_contract.json` matching the wire path the app bundle uses.
- A fixture under `tests/fixtures/` with a real or redacted payload. Do not guess fixture shapes: capture one from the live API with `scripts/probe_farmad.py` and redact personal data before committing.
- A Bruno mirror in `.bruno/` whose docs name the client method it mirrors, satisfying `scripts/check_bruno_drift`.
- An entry under `[Unreleased]` in `CHANGELOG.md`.

## Captures and personal data

Captured payloads contain health data. Raw captures stay in `captures/`, which is git-ignored. Only redacted fixtures are committed. Synthetic names and identifiers for every person, every medication that is not a public product identifier, and every address.

## Test and repository rules

- Reuse `register_login_flow` from `tests/conftest.py` for login-flow tests.
- Pytest uses `asyncio_mode = auto`. Warnings are errors except the configured resource warnings.
- Ruff uses `select = ["ALL"]` with the documented ignore list in `pyproject.toml`. mypy runs in strict mode.
- Do not add narrative code comments. Docstrings document the public API.
- Never log tokens, credentials, or OAuth state.
- Run the text-quality skills over all user-facing text before committing: README, CHANGELOG entries, docstrings, and error messages. No em dashes, no semicolon-joined clauses, no filler transitions.
- Do not mention AI, agents, or tooling in commit messages.
