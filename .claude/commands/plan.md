---
description: Create a spec → task plan → checklist before any implementation. Always run this before touching code.
---

Given the user's request, produce the following in order — do NOT write any code yet:

## 1. Spec
3–5 bullets covering:
- What the feature/fix does and why
- Constraints and assumptions
- Edge cases to handle (empty states, errors, mixed data)

## 2. Task Plan
Numbered steps. Each step must name:
- The exact file(s) to create or modify
- What changes (add/edit/delete what)

Rules:
- No git add / commit / push steps — omit entirely
- No "test manually" steps — testing is the user's responsibility
- Stop at "implementation complete"

## 3. Self-Review Checklist
After implementation, Claude must verify:
- [ ] No cache/state overwrite bugs
- [ ] TypeScript check passes (hook runs automatically — confirm output is clean)
- [ ] Cross-position math normalizes currency
- [ ] All colors use CSS variables from `globals.css` — no hardcoded hex or Tailwind color literals
- [ ] Visualizations: trace through 3 cases — mixed currencies, single item, extreme aspect ratio

---

Wait for the user to approve the plan before implementing anything.
