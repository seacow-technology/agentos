# Task: C_DESKTOP_001

- title: Commercial Scenario: Product Shell tabs (Chat/Work/Coding/Projects/AWS/Tasks) load via embedded Console
- portal: desktop
- bucket: commercial/product_shell_navigation

## Context
- plan: /Users/pangge/PycharmProjects/AgentOS/frontend/reports/commercial_scenario_plan.md

## Scope
Verify Product Shell can switch between Chat/Work/Coding/Projects/AWS/Tasks without 404s, console errors, or broken assets. Embedded console must render without duplicate nav chrome.

## Hard Constraints
- Do not invent endpoints; use only repo evidence.
- If backend gap is confirmed, disable UI action with clear message and mark BLOCKED with evidence.
- Do not change auth flows, CI workflows, or mass-format.
- Do not manually edit anything under publish/webui-v2/.

## Acceptance
Run Playwright smoke against the running Desktop stack. Capture network + console evidence to frontend/reports/e2e_endpoint_evidence/C_DESKTOP_001.json and mark PASS only if 0 4xx/5xx (excluding favicon) and 0 console errors on each tab.

## Hints / Known Gaps
Product shell is apps/desktop-electron/resources/product-dist/app.js. Embedded Console is under /console/* with ?embed=1.
