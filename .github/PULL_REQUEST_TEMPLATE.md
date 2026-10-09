- [ ] `uv run python -m scripts.check` passes completely.
- [ ] The PR carries one of the seven labels: `breaking-change`, `new-feature`, `enhancement`, `bugfix`, `maintenance`, `documentation`, `dependencies`.
- [ ] Every commit subject follows the conventional commit format, so git-cliff renders it into `CHANGELOG.md`.

For endpoint changes, all of the following are present:

- [ ] A frozen `Endpoint` row in `src/aiofarmad/_endpoints.py` with the complete wire contract, including its api version.
- [ ] A typed `FarmadClient` method.
- [ ] A row in `tests/fixtures/farmad_app_contract.json` matching the wire path the app bundle uses.
- [ ] A redacted real payload under `tests/fixtures/`.
- [ ] A Bruno mirror whose request and docs satisfy `scripts.check_bruno_drift`.
