# Security Policy

## Reporting a vulnerability

Please report security issues privately so they can be fixed before a public
announcement.

- **Email:** savaisuthar678@gmail.com
- **GitHub:** use the private "Report a vulnerability" option on the
  [security advisory page](https://github.com/savai15/ins/security/advisories/new)

Please include:

- A description of the vulnerability and the affected version
- Steps to reproduce, if possible
- Impact and any suggested mitigation

## Scope

`ins` shells out to system package managers with elevated privileges
(`pkexec`/`sudo`). Anything that could cause unintended command execution,
privilege escalation, or unsafe file handling is in scope.

Out of scope: vulnerabilities in the underlying package managers themselves
(report those upstream), and issues requiring the attacker to already have
interactive terminal access to your account.

## Response

You will receive an acknowledgment within 48 hours. We aim to confirm or
address reported issues within 7 days, and coordinate disclosure after a fix
is released.
