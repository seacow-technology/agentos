# Business Validation Plan (Desktop)

This plan is the human-readable companion of `frontend/reports/business_validation_lock.json`.

## Task Buckets

1. `product_shell/modes`
   - Goal: Product Shell provides Chat / Work / Coding as first-class modes (Claude Cowork style), without leaking system complexity.
   - Status: DONE (see lock).

2. `console/embed`
   - Goal: WebUI Console can be mounted under `/console/*` and also embedded (no extra chrome).
   - Status: DONE (see lock).

3. `aws_ops`
   - Goal: Add AWS Ops entry that creates a chat session with aws context (profile/region) and safe starter prompts.
   - Status: DONE (see lock).

4. `projects`
   - Goal: Product Shell can open embedded Projects to manage real projects inside OctopusOS Desktop.
   - Status: DONE (see lock).

5. `playwright_smoke`
   - Goal: Real browser regression smoke for Product Shell + embedded Console tabs.
   - Status: DONE. Run: `npm run desktop:smoke:B_DESKTOP_005` (evidence: `frontend/reports/e2e_endpoint_evidence/B_DESKTOP_005.json`).
