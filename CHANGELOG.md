# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Before 1.0, breaking changes ship as minor bumps.

## [Unreleased]

### Changed

- Orders now model the real submitted-basket payload: pharmacy and customer comments, delivery state and location, payment state and total, the sales channel, the submission time, and product lines with multilingual descriptions. Fixtures come from a real capture, redacted by a repeatable pipeline in `scripts/_redact.py`.
- `FarmadClient.async_login` returns the issued token pair as `FarmadTokens`.

### Added

- Prescription reads through the Belgian eHealth service. The platform currently rejects non-browser clients for eHealth, so these calls raise `FarmadEhealthAuthorizationRequiredError`. The `ehealth_cookie` argument carries a consent session for the day Farmad relaxes that gate.

### Fixed

- The token endpoint answering a body that is not JSON raises `FarmadInvalidResponseError` instead of a raw `JSONDecodeError`.
- The built wheel ships the `LICENSE` file.

## [0.1.0] - 2026-10-01

### Added

- Scripted Auth0 login: PKCE, the hosted login form, the WS-Federation callback, and the rotating refresh token.
- Account, patient, and pharmacy reads with the pharmacy link exposed through the app's self-onboarding flow.
- Medication scheme reads for the daily scheme and the nondaily products.
- Messaging reads for conversations and their messages.
- Order reads and writes: baskets, the draft basket, order placement, and order cancellation.
- A pinned app contract in `tests/fixtures/farmad_app_contract.json` that validates every wire path and api version against the app bundle from build 13237.
