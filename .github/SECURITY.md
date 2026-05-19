# Security Policy

## Supported Versions

We currently provide security fixes for the following versions:

| Version | Supported |
|---|---|
| Latest (`main` branch) | Yes |
| Older releases | No — please update to latest |

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Doing so could expose users before a fix is available.

Instead, report vulnerabilities **privately** via one of these channels:

- **Email:** sahil@pgagi.in
- **GitHub Private Vulnerability Reporting:** Use the [Report a vulnerability](https://github.com/PG-AGI/toingg-jarvis/security/advisories/new) button on the Security tab of this repository.

### What to Include

To help us triage quickly, please provide:

1. A description of the vulnerability and its potential impact
2. Steps to reproduce or a proof-of-concept (without publicizing it)
3. Affected versions or components
4. Any suggested mitigations you've identified

### What to Expect

| Timeline | Action |
|---|---|
| Within 48 hours | Acknowledgment of your report |
| Within 7 days | Initial assessment and severity classification |
| Within 30 days | Fix developed and tested (complex issues may take longer) |
| After fix is released | Public disclosure coordinated with you |

We follow a **coordinated disclosure** policy. We'll work with you to agree on a disclosure timeline that gives users time to update before details are published.

### Rewards

Responsible disclosure of valid security vulnerabilities earns **200 points** in our [Contributor Reward System](../REWARD_SYSTEM.md) — in addition to public credit in the release notes (if you'd like it).

---

## Scope

Issues in scope:
- Credential or API key exposure in code or configs
- WebSocket connection vulnerabilities
- Arbitrary code execution via voice commands or browser automation
- Local privilege escalation

Out of scope:
- Issues in third-party dependencies (report those upstream)
- Issues requiring physical access to the machine
- Social engineering attacks
