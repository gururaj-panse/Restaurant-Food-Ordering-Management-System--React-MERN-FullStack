# Module 3 Development Plan
## Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Status:** Planning only. No application code modified.
**Basis:** `CURRENT_STATE.md`, `ARCHITECTURE_REQUIREMENTS.md`, `TARGET_ARCHITECTURE.md`, `TARGET_ARCHITECTURE_C4_DIAGRAM.md` (Rev. 2), `TARGET_ERD.md` (Rev. 2), `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md`, `MODULE_3_CURRENT_STATE_AND_GAPS.md`, and the existing RFOMS Jira backlog (Epic RFOMS-1, 18 Stories, 58 Sub-tasks).
**Ground rule:** every task below traces to an approved Module 2 decision, a confirmed repository fact, or an already-created Jira issue. Where Module 2 left something undecided, this plan says so explicitly rather than deciding it silently.

---

## 1. Target FastAPI Backend Structure

Module 2 approved the **module boundary** (five logical modules inside one FastAPI process — `TARGET_ARCHITECTURE_C4_DIAGRAM.md` Rev. 2) but explicitly left the **internal layering** undecided (`ARCHITECTURE_REQUIREMENTS.md` §8; `MODULE_3_CURRENT_STATE_AND_GAPS.md` gap #2). This plan proposes the minimal structure needed to execute the approved module boundary, marked **[PROPOSED — needs confirmation]** where it goes beyond what's already decided:

| Layer | Status | Source |
|---|---|---|
| One FastAPI app, one deployable process | **Approved** | `TARGET_ARCHITECTURE.md` §8; Jira RFOMS-3 |
| Five routers: `auth`, `user`, `restaurant`, `order`, `analytics` | **Approved** (matches current controller-file boundaries almost 1:1) | `TARGET_ARCHITECTURE_C4_DIAGRAM.md` Rev. 2; `MODULE_3_CURRENT_STATE_AND_GAPS.md` §11 |
| Data-access layer for `User`/`Restaurant`/`Order` | **Approved as a requirement, driver unnamed** | `PRD.md` BM-08; Open Question #12 |
| Routers → services → data-access split, vs. flat routers-call-DB-directly (mirroring current Express controllers) | **[PROPOSED — needs confirmation before Batch 1]** | Explicitly open per `ARCHITECTURE_REQUIREMENTS.md` §8 |
| Pydantic request/response models | **[PROPOSED — standard FastAPI convention, not yet approved as the validation strategy]** | Ties to Open Question #6 (validation-error shape) |
| `pytest` + FastAPI `TestClient`/`httpx` | **[PROPOSED — standard toolchain, not named by Module 2]** | Needed to satisfy PRD NFR-01 |

**Recommendation:** confirm the layering choice (flat vs. services) as the first decision of Batch 0, before any endpoint code is written, so all five modules are built consistently.

## 2. Migration Boundaries

- **In bounds:** the backend only (`food-ordering-backend` → new Python service). All 22 confirmed endpoints, the JWT/Google-OAuth auth mechanism, Stripe integration, Cloudinary integration, and the MongoDB data layer.
- **Out of bounds (explicit, per `BRD.md` §13 / `PRD.md` §10 / `BROWNFIELD_UI_UX_HANDOFF.md` §11):** any frontend code change (unless a specific, separately-approved decision requires a lockstep change — see Open Question #6); any database schema migration; any new business feature; any new payment, media, or identity provider; any navigation restructuring.
- **Unit of migration:** each of the five approved modules is a self-contained migration boundary — a module is "done" only when its endpoints, data access, and tests all pass together, per its Jira Story's acceptance criteria (§9 below).
- **Deployment boundary is unresolved** (Open Question #1/#13) — this plan sequences *code* migration; it does not assume a cutover mechanism.

## 3. Implementation Sequence

Directly reuses the already-approved Jira Epic structure (RFOMS-1) rather than inventing a new order — the dependency graph below **is** the RFOMS backlog's own dependency chain.

| Batch | Jira Story | What it delivers | Depends on |
|---|---|---|---|
| 0 | **RFOMS-2** | API contract freeze; resolve the 7 product-level open questions gating everything else | — |
| 1 | **RFOMS-3** | FastAPI scaffold: router skeleton, CORS, health endpoints, raw-body webhook exception, env loading | RFOMS-2 |
| 2 | **RFOMS-4** | MongoDB data-access layer for all 3 collections | RFOMS-3 |
| 3 | **RFOMS-5, -6, -7, -8** | Auth: password login/register/validate/logout → Google OAuth → auth dependency → user profile | RFOMS-4 |
| 4 | **RFOMS-9** | Restaurant & menu CRUD (incl. multipart, pence conversion, Cloudinary) | RFOMS-7, RFOMS-4 |
| 5 | **RFOMS-10** | Public restaurant discovery/search | RFOMS-4 |
| 6 | **RFOMS-11, -12, -13** | Order retrieval → checkout session → webhook handler | RFOMS-7, RFOMS-9, RFOMS-4 |
| 7 | **RFOMS-14, -15** | Restaurant-owner order management → analytics | RFOMS-9, RFOMS-2 |
| 8 | **RFOMS-16** | Point the unmodified frontend at the new backend; verify every integration point | All of the above |
| 9 | **RFOMS-17, -18, -19** | Test suite, documentation corrections, full regression pass | RFOMS-16 |

This is the same order already given in `PRD.md` §14 and the `TARGET_ARCHITECTURE_C4_DIAGRAM.md` recommendation — restated here as executable batches.

## 4. Existing Functionality That Must Be Preserved

*(Restated from `MODULE_3_CURRENT_STATE_AND_GAPS.md` §10 — not re-derived.)*

- All 22 endpoint paths, methods, request/response shapes, and status codes.
- JWT payload (`{userId}`), 1-day expiry, Bearer-header verification.
- Google OAuth authorization-code flow and its exact redirect query-parameter contract.
- Raw-body-before-JSON-parsing ordering for the Stripe webhook route.
- CORS allow-list.
- The three health endpoints (`/`, `/health`, `/api/health`).
- Pence-based currency conversion at the restaurant-write boundary.
- Cuisine `$all` (AND) filtering, fixed page size of 10, always-ascending sort.
- One-restaurant-per-user as an application-level-only guard (no DB constraint).
- The customer order-status filter (currently matches the full enum — effectively unfiltered).
- Global (not per-restaurant) analytics scope, pending Open Question #2.
- The Cloudinary upload mechanism, including the known lack of old-asset cleanup.

## 5. Database / Data-Access Work

**Maps to:** Jira Story **RFOMS-4** (3.1) and sub-tasks RFOMS-29–32; architecture decision: "MongoDB schema unchanged, no migration" (`MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §10); schema contract: `TARGET_ERD.md` Rev. 2.

- Implement data access for `User`, `Restaurant` (with embedded `menuItems`), `Order` (with embedded `cartItems`/`deliveryDetails`) — field names, types, and document shape unchanged.
- Preserve the two confirmed data gaps as-is unless RFOMS-2 resolves them: no `country` on `deliveryDetails`, no persisted `price` on `cartItems` items.
- Preserve the under-constrained references (`Restaurant.user`, `Order.restaurant`, `Order.user` not required) unless RFOMS-2 (Open Question #21) approves tightening them.
- **Blocking decision:** async MongoDB driver/ODM is unnamed (Open Question #12) — this must be resolved before RFOMS-4 can start in earnest.

## 6. API Migration Work

**Maps to:** Jira Stories RFOMS-5 through RFOMS-15 (all module stories); contract source of truth: `PRD.md` §8 and `BROWNFIELD_UI_UX_HANDOFF.md` §8 (per-endpoint request/response/error table).

Each of the 22 endpoints is migrated as a contract-preservation task, not a redesign: same path, same method, same request shape (including the specific multipart encoding for restaurant/menu writes), same response shape, same status codes for the same conditions. The four unauthenticated debug/test analytics endpoints are **not** assumed to be ported — their disposition is Open Question #3, gated behind RFOMS-2, and must be explicitly decided before RFOMS-15 is considered complete.

## 7. Authentication and Security Considerations

**Maps to:** Jira Stories RFOMS-5, -6, -7; `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §7 Security Architecture.

- Preserve JWT issuance/verification and Google OAuth exactly — no new identity provider (Auth0 explicitly excluded, per earlier confirmed decision).
- Preserve ownership-based authorization (no role field, no RBAC — none was requested).
- Preserve Stripe webhook signature verification as the sole trust mechanism for that one inbound external call.
- **Explicit decisions required, not defaults:** whether to retain or drop the dead `session_id` cookie fallback (RFOMS-41), whether to implement OAuth `state` validation (RFOMS-39), whether to fix the non-Stripe-error crash in checkout (RFOMS-55).
- **No new security controls** (rate limiting, security headers, additional sanitization) are in scope — none were confirmed as required by Module 1/2, and none are introduced by this plan.
- Secrets management for the target deployment is unresolved (Open Question #18) — this plan assumes environment-variable supply, matching current practice, pending that decision.

## 8. Testing Strategy

**Maps to:** Jira Story **RFOMS-17** (10.1) and sub-tasks RFOMS-68–71; requirement: `PRD.md` NFR-01 (baseline must exist; current state is 0%).

- **Contract tests** — one suite per module, asserting request/response shape parity against the endpoint table in `PRD.md` §8, using `pytest` + FastAPI's `TestClient`/`httpx` **[proposed, standard toolchain — not named by Module 2]**.
- **Business-rule tests** — pence conversion, cuisine AND-filter, one-restaurant-per-user guard behavior, order status enum, ownership checks — one test per confirmed rule in `CURRENT_STATE.md` §8.
- **Webhook signature tests** — valid and invalid-signature cases against the raw-body handling, since this is the highest-risk integration point in the system.
- **Coverage baseline** — established and reported, not compared against a numeric target, since no threshold was set (Open Question #10).
- No test strategy element here assumes a testing tool, CI pipeline, or coverage percentage beyond what's listed as proposed/standard above.

## 9. Validation Checkpoints

| Checkpoint | Gate |
|---|---|
| After Batch 0 (RFOMS-2) | All 7 product-level open questions resolved or explicitly deferred with an owner before any endpoint code is written |
| After Batch 1 (RFOMS-3) | Health endpoints reachable; CORS verified from an allowed origin; a manual raw-body webhook signature test passes against the scaffold |
| After each module batch (3–7) | The module's endpoints match `BROWNFIELD_UI_UX_HANDOFF.md` §8 row-for-row (request/response/status codes); the module's Jira Story acceptance criteria are met |
| Before Batch 8 (frontend integration) | All endpoint-implementation stories (RFOMS-5 through RFOMS-15) closed |
| After Batch 8 | Every journey in `BROWNFIELD_UI_UX_HANDOFF.md` §4 walked manually against the new backend with the unmodified frontend |
| Before calling Module 3 complete | RFOMS-19 regression pass complete; test-coverage baseline reported (not just "some tests exist") |

## 10. Git / Jira Evidence Required Per Implementation Batch

For each batch (§3), the following evidence is expected before the corresponding Jira Story is transitioned to Done:

1. **Jira Story and all its Sub-tasks** moved through the board to Done, with the Story's stated Acceptance Criteria checked off in a comment or description update.
2. **Commit messages reference the Jira key** (e.g., `RFOMS-9: implement restaurant create/update with multipart parsing`) so history is traceable to the backlog.
3. **A pull request per Story** (or per closely-related group of Sub-tasks), scoped to only that module's files — no unrelated file changes bundled in, consistent with this plan's migration-boundary-per-module principle (§2).
4. **Test results attached or linked** in the PR — the relevant contract/business-rule/webhook tests for that module, passing.
5. **A short contract-parity note** in the PR description confirming the endpoint(s) match their row in `PRD.md` §8 / `BROWNFIELD_UI_UX_HANDOFF.md` §8 — explicitly calling out any deviation and which open question it's gated behind.
6. **No silent resolution of an open question** — if a PR touches one of the items in §7 or the debug-endpoint decision (§6), the PR description must state which decision it implements and link back to the RFOMS-2 sub-task that approved it.

---

## Traceability — Task to Module 2 Decision

| Development task | Module 2 architecture decision it implements |
|---|---|
| 5 routers matching current controller files | `TARGET_ARCHITECTURE_C4_DIAGRAM.md` Rev. 2 — 5-module backend boundary |
| Order & Payment kept in one module | `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §10 — "Order and Payment kept in one module" decision, confirmed by current code coupling |
| MongoDB schema unchanged | `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §10 — "MongoDB schema unchanged, no migration" |
| JWT + Google OAuth, no Auth0 | `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §10 — explicit identity-provider decision |
| Raw-body webhook handling | `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §10 — "Raw-body webhook handling preserved exactly" |
| No queue/cache/orchestration introduced | `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §10 — "No queue, cache, or orchestration introduced" |
| Frontend receives no code changes by default | `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md` §12 — assumption, with the stated lockstep exception |

---

**Not decided by this plan:** the flat-vs-layered internal structure (§1), the MongoDB driver/ODM (§5), the migration/cutover strategy and rollback plan, the deployment platform, and every product-level open question gated behind RFOMS-2. Each is named explicitly above rather than assumed.
