# Business Requirements Document (BRD)
## Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Sources:** `CURRENT_STATE.md` (code-verified current-state analysis) and `BUSINESS_PROBLEM_STATEMENT.md` (reviewed and verified business problem statement). All labels below follow the convention: **Confirmed** (traced to `CURRENT_STATE.md`), **Proposed** (new requirement introduced by this modernization), **Assumption** (unverified, explicitly flagged), **Open Question** (unresolved, needs a decision-maker).

---

## 1. Business Context

BigHungers is an operating restaurant food-ordering platform. **(Confirmed)** It runs on a MERN-family stack: a React/TypeScript frontend, a Node.js/Express/TypeScript backend, and MongoDB as the data store, supporting customer browsing and ordering, Stripe-based payment, restaurant-owner menu/order management, and a business analytics dashboard.

The organization has decided to standardize backend implementation on Python/FastAPI. **(Assumption)** This decision is an external business/organizational input to the project — it is not a response to a proven defect in the current system. No performance problems and no security incidents have been identified in the codebase during this analysis.

## 2. Business Goals

1. Replace the Node.js/Express/TypeScript backend with a Python/FastAPI backend that is functionally equivalent to the current system. **(Proposed, derived from `BUSINESS_PROBLEM_STATEMENT.md` §7)**
2. Preserve every confirmed current business workflow — browsing, checkout/payment, order tracking, restaurant management, and analytics — without requiring any change to the existing frontend. **(Proposed)**
3. Establish an automated test baseline for backend behavior, since none currently exists. **(Proposed, addressing the confirmed gap in `CURRENT_STATE.md` §10)**
4. Resolve the confirmed ambiguity around the current production deployment target before cutover planning begins. **(Proposed, addressing `CURRENT_STATE.md` §2 finding)**
5. Route any deviation from current confirmed behavior through an explicit business/product decision rather than an implicit engineering choice made during the rewrite. **(Proposed)**

## 3. Stakeholders

| Stakeholder | Role in this project | Source |
|---|---|---|
| Customers | End users of browsing, ordering, payment, and order-tracking workflows — must experience no functional change. | Confirmed, `CURRENT_STATE.md` §1 |
| Restaurant owners/managers | Manage restaurant profile, menu, and incoming orders — must experience no functional change. | Confirmed, `CURRENT_STATE.md` §1 |
| Business/platform stakeholders | Consume the analytics dashboard (currently global across all restaurants, not owner-scoped). | Confirmed, `CURRENT_STATE.md` §8 |
| Engineering team | Builds and validates the FastAPI backend; owns introducing the test baseline. | Confirmed (current maintenance burden), Proposed (new responsibility) |
| Business/product owner | Accountable approver for any deviation from current confirmed behavior (see open questions). | Proposed, per `BUSINESS_PROBLEM_STATEMENT.md` open question 7 |
| Infrastructure/operations owner | Confirms actual current production deployment target (Render/Netlify vs. Coolify). | Open Question, `CURRENT_STATE.md` §2 |

## 4. Business Requirements

| ID | Requirement | Rationale |
|---|---|---|
| BR-1 | Reimplement all 22 confirmed API endpoints in FastAPI with equivalent request/response contracts. | `CURRENT_STATE.md` §3 — frontend depends on exact contracts; no frontend changes are permitted. |
| BR-2 | Preserve MongoDB as the system of record; no database engine or schema migration. | `BUSINESS_PROBLEM_STATEMENT.md` §11; `CURRENT_STATE.md` §4. |
| BR-3 | Preserve JWT-based authentication mechanics (payload shape, 1-day expiry, Bearer header) and the existing server-side Google OAuth flow. | `CURRENT_STATE.md` §5 — frontend depends on unchanged token behavior. |
| BR-4 | Preserve Stripe Checkout session creation and webhook signature verification, including raw-body handling. | `CURRENT_STATE.md` §6 — checkout is the revenue-critical path. |
| BR-5 | Preserve Cloudinary-based restaurant image upload behavior. | `CURRENT_STATE.md` §7. |
| BR-6 | Preserve all confirmed current business rules (integer-pence currency handling, cuisine `$all` filter, ownership checks, etc.) unless explicitly approved otherwise. | `CURRENT_STATE.md` §8. |
| BR-7 | Make no changes to the existing frontend application. | `BUSINESS_PROBLEM_STATEMENT.md` §13, explicit constraint. |
| BR-8 | Establish an automated test baseline sufficient to validate behavioral parity, since none exists today. | `CURRENT_STATE.md` §10 (confirmed zero-test-suite); `BUSINESS_PROBLEM_STATEMENT.md` §9. |
| BR-9 | Confirm and document the actual current production deployment target before cutover planning. | `CURRENT_STATE.md` §2 finding; open question 1. |
| BR-10 | Route any deviation from current confirmed behavior (analytics scoping, debug endpoints, dropped `country` field, inconsistent validation shapes) through explicit business/product owner approval. | `BUSINESS_PROBLEM_STATEMENT.md` open questions 2–5, §13. |

## 5. Scope

**In scope (business level):**
- Full backend reimplementation covering every confirmed route group: authentication, user profile, restaurant management (owner), public restaurant discovery, orders/payments, and business analytics.
- Continuity of the existing MongoDB data store and its collections.
- Continuity of existing third-party integrations: Stripe, Cloudinary, Google OAuth.
- Introduction of automated tests to validate the migration.

**Out of scope (business level):**
- Any frontend redesign or frontend code change.
- Any database engine migration.
- New business features not present in the current system.
- Changing the payment provider, file-storage provider, or identity provider.
- Performance optimization not tied to preserving current behavior.
- Silent resolution of open product questions (analytics scoping, debug-endpoint disposition) — these require explicit sign-off, not a default choice made during the rewrite.

*(Source: `BUSINESS_PROBLEM_STATEMENT.md` §12–§13.)*

## 6. Success Criteria

- 100% of the 22 confirmed endpoints reimplemented with functionally equivalent request/response contracts.
- Zero required frontend code changes to operate against the new backend, unless a change is explicitly approved.
- All confirmed workflows (search, checkout/payment, order tracking, restaurant management, analytics) verified functionally equivalent post-migration.
- A defined, non-zero automated test coverage baseline established for the new backend (starting point: 0% today, confirmed).
- No data loss and no required schema migration for existing MongoDB collections.
- Stripe webhook signature verification continues to succeed against the existing `STRIPE_WEBHOOK_SECRET` configuration.

*(Source: `BUSINESS_PROBLEM_STATEMENT.md` §9.)*

## 7. Risks and Assumptions

| # | Item | Type | Source | Business severity | Mitigation / Owner |
|---|---|---|---|---|---|
| 1 | No automated test suite exists today; migration could introduce undetected regressions in revenue-critical flows (e.g., checkout). | Risk | `CURRENT_STATE.md` §10 | High | Build a parity test suite covering all 22 endpoints before cutover; owner: engineering lead. |
| 2 | Current production deployment target is ambiguous (Render/Netlify vs. Coolify signals coexist in the repo). | Risk | `CURRENT_STATE.md` §2 | Medium | Confirm with infrastructure/operations owner before cutover planning. |
| 3 | Confirmed frontend/backend contract gaps (dropped delivery `country`, inconsistent validation error shapes) could cause disagreement mid-project if not resolved upfront. | Risk | `CURRENT_STATE.md` §4, §9 | Medium | Resolve as explicit open questions before implementation begins; obtain business sign-off. |
| 4 | Several analytics endpoints are currently unauthenticated; carrying them forward without a decision extends unreviewed surface area into the new system. | Risk | `CURRENT_STATE.md` §3 | Medium | Require an explicit product decision (open question 4) before porting these endpoints. |
| 5 | The decision to standardize on Python/FastAPI is presumed to be driven by team/ecosystem alignment, not a proven system defect. | Assumption | `BUSINESS_PROBLEM_STATEMENT.md` §10 | Low | Define measurable success metrics up front (see §6) so the benefit is verifiable post-migration. |
| 6 | Current MongoDB connectivity, data volume, and integrity are assumed stable and reachable from a Python driver; this was not verified since the application was not run during analysis. | Assumption | Not runtime-verified | Low | Verify database connectivity and credentials early in implementation. |
| 7 | Stripe, Cloudinary, and Google remain the payment, media, and identity providers respectively. | Assumption | `BUSINESS_PROBLEM_STATEMENT.md` §10 | Low | Confirm no provider change is planned before implementation begins. |
