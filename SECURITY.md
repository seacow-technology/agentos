# Security Policy

## Supported Versions

AgentOS is currently in **early-stage development**.

Only the **latest release on the default branch** is supported for security reporting.  
Older releases and development snapshots may not receive security fixes.

---

## Reporting a Vulnerability

If you discover a security vulnerability in AgentOS, **please do not open a public issue**.

Instead, report it privately using one of the following methods:

- GitHub Security Advisories (preferred)
- Email: **security@seacow.tech** *(replace with your preferred contact if needed)*

When reporting, please include:
- A clear description of the vulnerability
- Steps to reproduce (if applicable)
- Potential impact and risk assessment
- Any suggested mitigation or fix

You will receive an acknowledgment within a reasonable timeframe.

---

## Responsible Disclosure

We follow a **responsible disclosure** process:

- Security reports are reviewed privately
- Fixes are developed and validated before public disclosure
- Credit may be given to reporters upon request

Please allow time for investigation and remediation before public discussion.

---

## Security Scope

AgentOS is designed to run **locally or in private environments**.

Out of scope:
- Misconfiguration of user environments
- Exposed deployments on public networks
- Third-party model or provider vulnerabilities

In scope:
- Remote code execution risks
- Privilege escalation
- Data leakage
- Unsafe default configurations
- Injection or sandbox escape vectors

---

## Deployment Warnings

⚠️ **Do not expose AgentOS directly to the public internet.**

AgentOS does **not** include:
- Authentication systems
- Multi-tenant isolation
- Hardened sandboxing guarantees

If you deploy AgentOS in shared or network-accessible environments, you are responsible for additional security controls.

---

## Security Philosophy

AgentOS prioritizes:
- Explicit execution boundaries
- Observability over hidden behavior
- Failsafe defaults over convenience

Security hardening improves incrementally as the project evolves.

---

Thank you for helping keep AgentOS and its users safe.
