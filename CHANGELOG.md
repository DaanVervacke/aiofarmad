# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Before 1.0, breaking changes ship as minor bumps.

## [Unreleased]

### Maintenance

- Allow uv 0.13

## [0.6.1] - 2026-10-10

### Bug Fixes

- Raise FarmadTimeoutError when a token request times out

### Documentation

- Fix guide, contributor, and Bruno drift
- Fix PR template, changelog steps, and redaction docstring

## [0.6.0] - 2026-10-09

### Breaking Changes

- Drop the unused PharmacyLinkResult model

### Bug Fixes

- Reject non-object answers from single-object endpoints
- Map an undecodable or failing login page to library errors
- Keep not-found-is-none after a token refresh retry
- Report a pending pharmacy link and accept an explicit account id
- Send the app user agent on token requests

### Documentation

- Complete the readme against the current client
- Correct the guides and add reading and error pages
- Fix template, contributor, and changelog drift

### Features

- Raise a dedicated error for a missing account or patient id
- Pass a redirect url when submitting an online-paid order

### Maintenance

- Bump release-drafter/release-drafter (#2)

## [0.5.0] - 2026-10-02

### Features

- Port the remaining customer endpoints and pin the bundle ledger

## [0.4.0] - 2026-10-02

### Features

- Search products at one pharmacy with a search term

## [0.3.0] - 2026-10-02

### Features

- Complete multi-factor logins with a one-time code provider

## [0.2.0] - 2026-10-02

### Features

- Resolve a CNK or GTIN to the product at one pharmacy

## [0.1.0] - 2026-10-02

### Bug Fixes

- Map bad token bodies, ship the wheel license, drop dead code
- Repair the pinned upload-artifact revision in the release workflow

### Documentation

- Describe the eHealth browser session gate

### Features

- Create the aiofarmad library
- Add prescription reads through the eHealth consent session
- Model the real submitted order from a live capture

### Maintenance

- Complete the uv toolchain migration
- Strip the workflow version comments
- Migrate the release drafter config and label workflows
- Manage the changelog with git-cliff

[Unreleased]: https://github.com/DaanVervacke/aiofarmad/compare/v0.6.1...HEAD
[0.6.1]: https://github.com/DaanVervacke/aiofarmad/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/DaanVervacke/aiofarmad/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/DaanVervacke/aiofarmad/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/DaanVervacke/aiofarmad/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/DaanVervacke/aiofarmad/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/DaanVervacke/aiofarmad/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/DaanVervacke/aiofarmad/releases/tag/v0.1.0
