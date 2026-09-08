# Security Policy

Thank you for helping keep AddrLens and its users safe. This document explains how to report vulnerabilities responsibly.

## Supported versions

Only the current `main` branch is maintained. The live deployment at [addrlens.de](https://addrlens.de) tracks `main`. Older tagged releases do not receive security patches — please update to `main` before reporting an issue against them.

| Version         | Supported          |
|-----------------|--------------------|
| `main` (live)   | ✅ Yes             |
| Any older tag   | ❌ No              |

## Reporting a vulnerability

**Please do not open a public GitHub Issue or discuss the vulnerability in public forums, chat rooms, or social media until it has been fixed and disclosed.**

Two channels, in order of preference:

1. **GitHub Private Vulnerability Reporting** — on the repository, use *Security → Report a vulnerability*. This creates a private advisory only the maintainer can see.
2. **Email** — `informsapta@gmail.com` with subject line `[SECURITY] <short summary>`.

Whichever channel you use, please include:

- A clear description of the vulnerability and its impact.
- Steps to reproduce (a minimal proof-of-concept is ideal; a curl command against the live site is fine).
- Affected version / commit SHA and, if relevant, browser + OS.
- Your suggested severity (`low` / `medium` / `high` / `critical`) and any CVSS 3.1 vector you have in mind.
- Whether you would like public credit in the fix advisory, and under what name.

If you need to send encrypted material, request a PGP key over the same channel and one will be provided.

## Response timeline

- **Acknowledgement:** within 72 hours of receipt.
- **Initial assessment + severity confirmation:** within 7 days.
- **Fix or mitigation for actionable findings:** within 14 days for `high` / `critical`, within 30 days for `medium` / `low`.
- **Public disclosure:** coordinated with the reporter. Default is to publish a GitHub Security Advisory once the fix has shipped to the live site.

If the timeline slips, you will hear from me before the deadline passes.

## Scope

**In scope:**

- The live application at `addrlens.de` and any subdomain served by this repository (`api.addrlens.de`, future city subdomains, etc.).
- All code in this repository under `v0.1/` (production tree) — `app/`, `inference/`, `web/`, `ops/`, `scripts/`, deployment manifests.
- All JSON endpoints under `/api/*` and static assets under `/static/*`.

**Explicitly out of scope:**

- Third-party services AddrLens depends on — Berlin Geoportal WFS endpoints, OpenStreetMap Overpass, Cloudflare (CDN, Tunnel, Workers AI), Hetzner, Sentry, Umami hosting infrastructure. Report those to the respective vendors.
- Vulnerabilities that require compromised user devices, phishing, physical access, or social engineering of the maintainer.
- Denial-of-service against the free public deployment. The per-IP rate limiter in `v0.1/app/core/rate_limit.py` is the intended protection layer; please do not run load tests against the live site without prior arrangement.
- The archived prototype trees at [`docs/history/prototypes/`](docs/history/prototypes/) (`phase0/`–`phase3/`) — historical reference artefacts, not deployed.
- Findings on `.local`, `localhost`, or personal fork deployments unless they are reproducible on `addrlens.de`.

## Safe harbour

Good-faith security research is welcome. If you follow this policy:

- No legal action will be pursued against you for accessing your own account, testing on your own dataset, or performing non-destructive reconnaissance limited to what is necessary to demonstrate the vulnerability.
- Do not access, modify, or exfiltrate data belonging to other users. Do not degrade the service for other users. Do not persist test payloads (delete them or tell us where they are so we can clean up).
- If in doubt about whether an action is safe, ask first via the reporting channels above.

## Recognition

Reporters who follow this policy will be credited in the published advisory (unless you prefer to remain anonymous) and — where the fix is user-visible — in the `CHANGELOG.md` entry for the release that ships the fix.

There is no monetary bug bounty programme at this time.

## Non-security bugs

For regular bugs, feature requests, or documentation issues, please open a public [GitHub Issue](https://github.com/saptadip/addrlens/issues) — see [CONTRIBUTING.md](CONTRIBUTING.md) for what to include.
