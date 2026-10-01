# Security policy

## Supported versions

Only the latest release line receives security fixes.

## Reporting a vulnerability

Report vulnerabilities privately through [GitHub security advisories](https://github.com/DaanVervacke/aiofarmad/security/advisories/new).
Do not open a public issue for a vulnerability.

You will get a response within a week. Include reproduction steps and affected versions where you can.

## Scope

This library talks to the Farmad Procura API with credentials you own. Treat every access token and refresh token as a secret: tokens grant access to your medication history, your prescriptions, and your pharmacy orders.

Never commit credentials, tokens, or captured response payloads that contain personal health data. The `.env` file and the `captures/` directory are git-ignored for exactly this reason.
