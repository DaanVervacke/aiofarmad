# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Before 1.0, breaking changes ship as minor bumps.

## [Unreleased]

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
