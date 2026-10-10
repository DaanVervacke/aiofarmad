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

Coverage measures branches in `src/` and requires `fail_under = 98`. `uv audit` needs network access. `scripts.check_bundle_ledger` compares the contract ledger with the captured app bundle at `captures/farmad_main_2ba421e258d1f7c6.js`. Without that file it prints `skipped` and passes, so CI never runs the comparison.

The Sphinx docs build with `uv run --group docs sphinx-build -W -b html docs docs/_build/html`. Read the Docs builds them with warnings as errors, and the check gate does not build them.

## Adding an endpoint

Add all of the following:

- A frozen `Endpoint` row in `_endpoints.py` with the complete wire contract, including its api version.
- A typed `FarmadClient` method.
- A row in `tests/fixtures/farmad_app_contract.json` matching the wire path the app bundle uses.
- A fixture under `tests/fixtures/` from a real payload, redacted. Do not guess fixture shapes: capture one from the live API with `uv run python -m scripts.capture_data`, which writes each payload into `captures/` as `<name>_raw.json`. For a payload it does not cover yet, add the request to its `calls` list first. Then add a row to `REDACTIONS` in `scripts/_redact.py` and run `uv run python -m scripts._redact`, which rewrites each listed fixture from its raw capture with synthetic personal data. The eHealth fixtures `prescriptions.json` and `prescription.json` are placeholders, because no consented session has been captured. Replace them with a redacted capture once `scripts.capture_ehealth` succeeds.
- A Bruno mirror in `.bruno/` whose docs contain `Mirrors FarmadClient::<method>`, satisfying `scripts/check_bruno_drift`.
- A conventional commit subject, which git-cliff renders into `CHANGELOG.md`.

## Changelog

`CHANGELOG.md` is generated with git-cliff from conventional commit subjects. Never edit it by hand. Features, bug fixes, documentation, and maintenance chores reach the changelog through their `feat:`, `fix:`, `docs:`, and `chore:` subjects. A subject with `!` after the type, such as `refactor!:`, lands under Breaking Changes. Other types without a `!` stay out of the changelog. Regenerate the whole file with `git-cliff --output CHANGELOG.md` and commit the result as `chore: regenerate the changelog`, which git-cliff leaves out of the changelog. At release, set the version with `uv version X.Y.Z`, cut the dated section with `git-cliff --tag vX.Y.Z --output CHANGELOG.md`, and commit `pyproject.toml`, `uv.lock`, and `CHANGELOG.md` as `chore: release X.Y.Z`. git-cliff leaves that commit out of the changelog. Then publish the GitHub release that release-drafter prepared, tagged `vX.Y.Z`. The release workflow refuses a tag that does not match the `pyproject.toml` version. A full regeneration keeps the version link definitions at the bottom of the file current, which `--prepend` does not.

## Live scripts

The scripts below call the real Farmad API. They read `EMAIL` and `PASSWORD` from a local `.env` file. Every script except `scripts.capture_ehealth` targets the pharmacy in its `APB` constant, so change that constant to a pharmacy your account is linked to.

- `scripts.capture_data` dumps the main read payloads into `captures/`, except the draft basket and the eHealth reads.
- `scripts.probe_farmad` runs the main read endpoints through the client.
- `scripts.capture_ehealth` retests the eHealth gate and also needs `EHEALTH_COOKIE` in `.env`.
- `scripts.place_test_order` submits a real order to the pharmacy and then cancels it.

Run each one with `uv run python -m scripts.<name>`.

The Bruno environments in `.bruno/environments/` read their secrets from `FARMAD_ACCESS_TOKEN`, `FARMAD_REFRESH_TOKEN`, `FARMAD_APB`, `FARMAD_ACCOUNT_ID`, `FARMAD_PATIENT_ID`, and `FARMAD_EHEALTH_COOKIE` in the process environment.

## Captures and personal data

Captured payloads contain health data. Raw captures stay in `captures/`, which is git-ignored. Only redacted fixtures are committed. Fixtures use synthetic names and identifiers for every person, every medication that is not a public product identifier, and every address.

## Test and repository rules

- Reuse `register_login_flow` from `tests/conftest.py` for login-flow tests.
- Pytest uses `asyncio_mode = auto`. Every warning is an error, including an unclosed session.
- Ruff uses `select = ["ALL"]` with the documented ignore list in `pyproject.toml`. mypy runs in strict mode.
- Do not add narrative code comments. Docstrings document the public API.
- Never log tokens, credentials, or OAuth state.
- Run the text-quality skills over all user-facing text before committing: README, commit subjects, docstrings, and error messages. No em dashes, no semicolon-joined clauses, no filler transitions.
- Do not mention AI, agents, or tooling in commit messages.
