# Task: B_DESKTOP_005

- title: Playwright smoke for product shell + embedded console
- portal: desktop
- bucket: playwright_smoke

## Context
- plan: /Users/pangge/PycharmProjects/AgentOS/frontend/reports/business_validation_plan.md

## Scope
Add a minimal playwright smoke that boots backend + serves proxy, then verifies Product Shell tabs can load embedded console routes without 404 console errors.

## Hard Constraints
- Do not invent endpoints; use only repo evidence.
- If backend gap is confirmed, disable UI action with clear message and mark BLOCKED with evidence.
- Do not change auth flows, CI workflows, or mass-format.
- Do not manually edit anything under publish/webui-v2/.

## Acceptance
A single command produces deterministic PASS/FAIL and stores evidence under frontend/reports/e2e_endpoint_evidence/B_DESKTOP_005.json.

## Hints / Known Gaps
Prefer CLI-first using existing apps/webui e2e harness or add a small Node harness to start runtime + proxy.
