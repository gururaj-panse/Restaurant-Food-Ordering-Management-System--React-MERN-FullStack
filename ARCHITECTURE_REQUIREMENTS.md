# Architecture Requirements Document (ARD)
## Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Module:** 2 — Architecture & Solution Design
**Sources:** `BRD.md`, `PRD.md`, `CURRENT_STATE.md`, `BUSINESS_PROBLEM_STATEMENT.md`, `BROWNFIELD_UI_UX_HANDOFF.md`, RFOMS Jira backlog (Epic RFOMS-1).

**How to read this document:** Every requirement is tagged **[CURRENT STATE]** (what exists today, confirmed from the repository), **[TARGET STATE]** (what the modernized backend must do, derived from BRD/PRD), or **[Open Question]** (undecided — not to be silently resolved). Each item cites its source. This document defines *requirements* the target architecture must satisfy — it does not select frameworks, libraries, or draw the target architecture itself, beyond what is already mandated (Python/FastAPI, MongoDB retained).

---

## 1. Architecture Overview

**[CURRENT STATE]** A single-process monolith: a React/TypeScript SPA frontend calling a Node.js/Express/TypeScript backend, which talks directly to MongoDB and to three external services (Stripe, Cloudinary, Google OAuth) with no intermediary layers — no API gateway, no message queue, no cache, no background job runner. *(CURRENT_STATE.md §2, §6, §7)*

**[TARGET STATE]** The same overall shape — one backend service, same three external integrations, same MongoDB data store — with the Express implementation replaced by FastAPI. The frontend, the database engine, and the external providers are explicitly **not** changing. *(BRD.md §2 Goal 1–2, PRD.md §1)*

**[Open Question]** Whether the target retains a single-process monolith or introduces internal service boundaries is not addressed in Module 1 material — no such change was requested, and BRD.md §13/PRD.md §10 explicitly place "new business features" and "major navigation restructuring" out of scope, which implies no architectural expansion was intended, but this has not been explicitly confirmed as an architecture constraint.

## 2. Business Goals

*(BRD.md §2, traceable to BUSINESS_PROBLEM_STATEMENT.md §7)*

1. Replace the Node.js/Express/TypeScript backend with a functionally equivalent Python/FastAPI backend.
2. Preserve every confirmed business workflow without requiring frontend changes.
3. Establish an automated test coverage baseline (0% today).
4. Resolve the current production deployment ambiguity before cutover.
5. Route any deviation from current confirmed behavior through explicit business/product approval.

## 3. Modernization Goals

*(PRD.md §7 Modernization Objectives, cross-referenced to BRD.md §4 Business Requirements)*

1. Reimplement all 22 confirmed API endpoints with equivalent request/response contracts.
2. Preserve MongoDB as the system of record — no database migration.
3. Preserve JWT authentication mechanics and the server-side Google OAuth flow.
4. Preserve Stripe Checkout Session creation and webhook signature verification, including raw-body handling.
5. Preserve Cloudinary-based image upload behavior.
6. Preserve all confirmed business rules unless a deviation is explicitly approved.
7. Introduce automated tests as part of the modernization itself (a new deliverable, not a preserved behavior).

## 4. User Roles and Actors

**[CURRENT STATE]** *(CURRENT_STATE.md §4, §5; BROWNFIELD_UI_UX_HANDOFF.md §3)*

| Actor | Nature | Notes |
|---|---|---|
| Guest (unauthenticated visitor) | Human | Can browse, search, view restaurant details, view public analytics. |
| Authenticated user ("customer") | Human | Any user with a valid JWT. No `role` field exists on `User`. |
| "Restaurant owner" | Human, **not a distinct account type** | Implicit — any authenticated user who has created a `Restaurant` document with `user === their id`. Enforced per-request in controllers, not by a schema role. |
| Business/platform stakeholder | Human | Views the analytics dashboard, which is global (not scoped to a specific restaurant) and public. |
| Stripe | External system actor | Calls the webhook endpoint server-to-server; verified by signature, not JWT. |
| Google | External system actor | OAuth identity provider; backend exchanges codes and fetches userinfo. |
| Cloudinary | External system actor | Receives uploaded images, returns hosted URLs. |

**[TARGET STATE]** The same actor model is required to be preserved — no new roles, no role-based access control system is requested. *(BRD.md §13 out-of-scope: "major navigation restructuring"; PRD.md §10: no new features)*

**[Open Question]** Whether a formal role model (e.g., `role` field, RBAC) should be introduced is not requested anywhere in Module 1 material and must not be added without approval.

## 5. Major User Journeys

**[CURRENT STATE, to be preserved unchanged in TARGET STATE]** *(BROWNFIELD_UI_UX_HANDOFF.md §4, full detail there)*

1. Customer signs in (password or Google OAuth).
2. Customer searches for a restaurant (by city, cuisine, keyword).
3. Customer views restaurant details and menu.
4. Customer selects food items (client-side cart, `sessionStorage`).
5. Customer checks out (Stripe Checkout redirect).
6. Customer views order history.
7. Customer tracks an order (polled status, 5s interval).
8. Restaurant owner signs in (same mechanism as customer).
9. Restaurant owner creates/updates a restaurant and its menu.
10. Restaurant owner views incoming orders and updates order status.
11. Business stakeholder views analytics (global scope, public).

Every journey's success/loading/empty/error state as currently implemented must continue to function identically post-migration. *(PRD.md §8 Acceptance Criteria; BROWNFIELD_UI_UX_HANDOFF.md §9)*

## 6. Functional Architecture Requirements

**[TARGET STATE]** *(PRD.md §3a "Preserved Functionality", §3b "Backend-Modernization-Specific Requirements")*

| Domain | Requirement |
|---|---|
| Auth | Support register, login, token validation, logout, and Google OAuth exchange with identical contracts (PF-01–PF-06). |
| User profile | Support get/update of the authenticated user's profile (PF-07–PF-09). |
| Restaurant management | Support create/update/read of an owner's restaurant, including image upload and menu items (PF-10–PF-14). |
| Public discovery | Support city listing, restaurant detail lookup, and filtered/sorted/paginated search (PF-15–PF-17). |
| Orders & payment | Support order retrieval, Stripe Checkout session creation, and webhook-driven status updates (PF-18–PF-20). |
| Analytics | Support authenticated and public analytics retrieval, identical global scope unless changed by approved decision (PF-21–PF-23). |
| Cross-cutting rules | Preserve pence-based currency handling, AND-semantics cuisine filtering, one-restaurant-per-user application-level guard, and the current (permissive) order-status filter behavior (PF-24–PF-27). |

**[TARGET STATE — modernization-specific]** *(PRD.md §3b)* The target backend must additionally:
- Expose identical route paths/prefixes/methods (BM-01).
- Read the raw request body for Stripe webhook signature verification before any JSON-parsing step (BM-02).
- Implement an auth dependency accepting `Authorization: Bearer <token>` (BM-03).
- Accept the exact multipart/form-data field encoding the frontend already sends (BM-05).
- Perform pounds-to-pence conversion at the API boundary (BM-06).
- Reproduce the CORS allow-list behavior (BM-07).
- Reproduce the three health-check endpoints (BM-09).
- Reproduce the Cloudinary upload mechanism (BM-10).

## 7. Non-Functional Requirements

### 7.1 Scalability
**[CURRENT STATE]** No scalability target, load figure, or concurrency requirement exists anywhere in Module 1 material. **[Open Question]** *(PRD.md §4 NFR-04: "No performance targets... are defined by this PRD, since none were confirmed as necessary or requested.")* The target architecture must not invent a scalability target; one should be requested from the business if needed.

### 7.2 Performance
**[CURRENT STATE]** No latency/throughput baseline was measured (the application was not executed during Module 1 analysis — `CURRENT_STATE.md` explicitly notes zero "Observed" findings). **[Open Question]** No performance requirement is defined for the target. *(PRD.md §4 NFR-04)*

### 7.3 Availability
**[CURRENT STATE]** No uptime SLA/SLO is documented. The existing `/health` endpoint computes uptime from an in-process start-time closure, which is explicitly noted as incorrect under a multi-instance deployment (`CURRENT_STATE.md` §2) — this is a confirmed current limitation, not a target requirement. **[Open Question]** No availability target is defined for the target state.

### 7.4 Security
**[CURRENT STATE]** *(CURRENT_STATE.md §5, §9)* JWT + bcrypt-equivalent password hashing; Stripe webhook signature verification; no rate limiting; no security-header middleware (e.g., no helmet equivalent); no centralized input sanitization beyond presence/type validation; several analytics endpoints are unauthenticated; the OAuth CSRF `state` parameter is generated but never validated.
**[TARGET STATE]** Preserve current authentication and webhook-verification security exactly. *(PRD.md §6, §7)* **No new security controls (rate limiting, security headers, additional sanitization) are required** — PRD.md NFR-05 explicitly states this is out of scope unless separately requested, and BRD/BUSINESS_PROBLEM_STATEMENT.md rule 4 prohibits inventing security requirements not evidenced. **[Open Question]** Whether to fix the unchecked OAuth `state` param and the unauthenticated debug endpoints is gated behind Jira Story RFOMS-2 (§1.1) and is not decided.

### 7.5 Maintainability
**[CURRENT STATE]** *(CURRENT_STATE.md §9)* Two inconsistent validation-error response shapes; no centralized/global error handler; ad hoc `console.log`/`console.error` instead of structured logging; no automated tests.
**[TARGET STATE]** *(PRD.md §4 NFR-01, NFR-02)* An automated test suite covering all 22 endpoints and confirmed business rules must exist before migration is considered complete. Whatever resolution is chosen for the validation-error-shape inconsistency must be applied uniformly (not decided yet — gated behind RFOMS-2).

### 7.6 Observability
**[CURRENT STATE]** *(CURRENT_STATE.md §9)* No request logging middleware (no morgan/pino equivalent); only scattered `console.log` calls, heaviest in the analytics controller. No metrics, tracing, or structured logging exists.
**[Open Question]** No observability requirement (structured logging, metrics, tracing) is specified anywhere in BRD/PRD for the target state. This must not be silently added as an architecture decision — it should be raised as an open question for the business/architecture owner before the target design assumes any specific tooling.

## 8. Major Application Components

**[CURRENT STATE]** *(CURRENT_STATE.md §2)* Single Express app (`src/index.ts`) → 6 route modules → 5 controllers (plain functions, no service layer) → Mongoose models (`User`, `Restaurant`, `Order`) → MongoDB. Two middleware modules: `auth.ts` (JWT verification) and `validation.ts` (express-validator chains).

**[TARGET STATE — component-level requirements only, not a design]** *(PRD.md §3b, §5–§7)* The replacement backend must provide, at minimum, logical equivalents of:
- An API/routing layer covering the same 6 route groups.
- An authentication dependency/middleware equivalent to `verifyToken`.
- A data-access layer for the three MongoDB collections.
- A payment-integration component wrapping Stripe (session creation + webhook handling).
- A media-upload component wrapping Cloudinary.
- A health/status component.

**[Open Question]** The specific Python web framework internals, project layout, async MongoDB driver/ODM (PRD.md BM-08 says only "an appropriate async Python driver/ODM," naming none), dependency-injection approach, and whether a service layer is introduced (which the current system lacks) are all undecided and reserved for the target architecture design step, not this requirements document.

## 9. External Systems and Integrations

**[CURRENT STATE, all confirmed]** *(CURRENT_STATE.md §6, §7, §5; BROWNFIELD_UI_UX_HANDOFF.md §5)*

| System | Purpose | Called from |
|---|---|---|
| Stripe | Payment processing (Checkout Sessions + webhook) | Backend only |
| Cloudinary | Restaurant image hosting | Backend only |
| Google OAuth | Identity provider for social sign-in | Backend (token/userinfo endpoints via server-side HTTP calls) |
| MongoDB | Primary data store | Backend only |
| robohash.org | Default avatar image fallback | **Frontend only** — called directly from the browser, bypassing the backend entirely; no backend involvement or configuration |

**[TARGET STATE]** All four backend-side integrations (Stripe, Cloudinary, Google, MongoDB) must be preserved with equivalent configuration surfaces (same env var names, per `CURRENT_STATE.md`'s environment inventory). No new external system is introduced. *(BRD.md §13, PRD.md §10: "no provider changes")*

## 10. Data Requirements

**[CURRENT STATE, confirmed]** *(CURRENT_STATE.md §4)*

- Three collections: `User`, `Restaurant` (with embedded `menuItems` subdocuments), `Order`.
- `User.email` is the only unique-indexed field; no role field.
- `Restaurant.deliveryPrice` and `menuItems[].price` are integer pence.
- `Order.totalAmount` is integer pence; `Order.deliveryDetails` has **no `country` field** despite the frontend collecting and sending one; `Order.cartItems` has **no persisted per-line price**.
- No database-level uniqueness constraint on `Restaurant.user` (one-restaurant-per-user is an application-level check only, with a known race-condition characteristic).

**[TARGET STATE]** *(PRD.md §3a PF-24–PF-27, BRD.md §11)* Document shape, field names, and types must be preserved exactly — no schema migration. Any change to the confirmed gaps (missing `country`, missing per-line price, missing uniqueness constraint) requires explicit approval, not a default "fix" during the port.

**[Open Question]** Whether to finally persist `country`, add per-line-item pricing, or add a database-level uniqueness constraint are all open decisions gated behind Jira Story RFOMS-2.

## 11. API/Integration Requirements

**[TARGET STATE]** *(PRD.md §5, §8 full contract table; BROWNFIELD_UI_UX_HANDOFF.md §8)* All 22 confirmed endpoints must be reproduced with:
- Identical method, path, and route prefix.
- Identical request body/query-parameter shapes and names.
- Identical response body shapes (including the `{url}` checkout response, `{cities:[]}`, `{data, pagination:{total,page,pages}}` search response, and the `AnalyticsData` shape).
- Identical HTTP status codes for identical conditions (400/401/404/409/500 usage patterns as currently implemented).

**[Open Question]** The four unauthenticated debug/test analytics endpoints (`/test`, `/db-test`, `/debug-orders`, `/debug-restaurants`) are not required to be ported — their disposition (port/secure/retire) is an open decision (PRD.md §5, gated behind RFOMS-2).

## 12. Authentication and Authorization Requirements

**[CURRENT STATE]** *(CURRENT_STATE.md §5)* JWT Bearer scheme, `{userId}` payload, 1-day expiry, bcrypt-hashed passwords (cost 8). Server-side Google OAuth (authorization-code exchange). Authorization is purely ownership-based (`Restaurant.user === req.userId`), re-checked per request in each controller — there is no centralized authorization layer or role system. A dead cookie-fallback path exists (`session_id`, never set). The OAuth `state` CSRF parameter is generated but never validated.

**[TARGET STATE]** *(PRD.md §6)* Preserve the JWT scheme (payload shape, expiry, Bearer header) and the Google OAuth flow exactly, since the frontend depends on them unchanged. **[Open Question]** Whether to retain or drop the dead cookie fallback, and whether to implement `state` validation, are open decisions (RFOMS-2 sub-tasks, PRD.md §6).

## 13. Payment Requirements

**[CURRENT STATE]** *(CURRENT_STATE.md §6)* Server-side Stripe Checkout Sessions, GBP-only (hardcoded in two places). Order is only persisted after Stripe returns a session URL. Webhook handles only `checkout.session.completed`; all other event types are acknowledged with no side effect. A confirmed bug: non-Stripe errors thrown during checkout crash the error handler (assumes `.raw.message` exists). `totalAmount` is written twice — a provisional app-computed value at session creation, then overwritten by Stripe's authoritative `amount_total` via webhook.

**[TARGET STATE]** *(PRD.md §7)* Preserve the Checkout Session creation contract, the raw-body webhook verification requirement, the pence-based/GBP-only calculation, and the "persist only after Stripe confirms" ordering. **[Open Question]** Whether to replicate or fix the non-Stripe-error crash bug, and whether to add handling for additional Stripe event types, are open decisions (RFOMS-2 sub-tasks).

## 14. Image/Media Requirements

**[CURRENT STATE]** *(CURRENT_STATE.md §7)* Multer with in-memory storage (no disk writes), 5MB size limit, no server-side file-type filter. Upload converts the buffer to a base64 data URI and calls `cloudinary.v2.uploader.upload()`, storing the returned plain-HTTP `.url` (not `.secure_url`). No cleanup of a previous image when a restaurant's image is replaced; no `public_id` stored, so retroactive cleanup is not possible from current data.

**[TARGET STATE]** *(PRD.md §7 BM-10)* Reproduce the upload mechanism (buffer→base64→upload) and the 5MB limit. Reproducing the exact multipart field name (`imageFile`) is required for frontend compatibility (§11 above). **[Open Question]** Whether to add old-asset cleanup or switch to `.secure_url` is not requested and would be a behavior change requiring approval.

## 15. Real-Time Order/Status Requirements

**[CURRENT STATE]** *(BROWNFIELD_UI_UX_HANDOFF.md §1, §4)* There is **no real-time mechanism** (no WebSockets, no Server-Sent Events, no push notifications) anywhere in the current system. All "live" behavior is client-side polling: order status polls `GET /api/order` every 5 seconds; restaurant-owner order management polls `GET /api/my/restaurant/order` every 5 seconds; the analytics dashboard polls every 30 seconds.

**[TARGET STATE]** *(PRD.md §3a, §6 — "Order status updates: No UI change... the frontend polls... it does not care how the backend computes status")* The target backend must continue to support polling-based status retrieval with data current enough for 5-second polling intervals to reflect changes. **No true real-time (push-based) mechanism is requested anywhere in Module 1 material.**

**[Open Question]** Whether the business wants to introduce genuine real-time updates (WebSockets/SSE) is not raised in any source document and must not be assumed as a target requirement.

## 16. Deployment Requirements

**[CURRENT STATE]** *(CURRENT_STATE.md §2, §10)* Two deployment-configuration lineages coexist in the repository: CORS entries and code comments pointing at Render + Netlify, versus a `Dockerfile` with comments pointing at Coolify (self-hosted). Which is actually live is **unconfirmed**. The existing backend Dockerfile uses a multi-stage Node build with a `/api/health` Docker `HEALTHCHECK`. Frontend has both `netlify.toml` and `vercel.json` committed.

**[TARGET STATE]** *(BRD.md §2 Goal 4, §7 risk #2)* The actual current production deployment target must be confirmed before cutover planning — this is an explicit business requirement (BR-9), not yet resolved.

**[Open Question]** Whether the target FastAPI backend will be containerized following the existing Docker pattern, and which platform will host it, are not decided in Module 1 material. This is reserved for target architecture design, contingent on resolving the deployment-target question first.

## 17. Technology Constraints

**[TARGET STATE — mandated]** *(BUSINESS_PROBLEM_STATEMENT.md, BRD.md §2 Goal 1)*
- Backend language/framework: **Python / FastAPI** (given, not derived).
- Database: **MongoDB retained**, no engine change (BRD.md §11).
- Frontend: **React/TypeScript/Vite retained**, no changes permitted (BRD.md §11).
- Payment provider: **Stripe retained**.
- Media provider: **Cloudinary retained**.
- Identity provider: **Google OAuth retained** (plus password-based JWT auth).

**[Open Question]** *(PRD.md §3b BM-08)* The specific async MongoDB driver or ODM for Python is explicitly left unnamed in PRD.md — this is a target-architecture-design decision, not a Module 1 output, and must not be silently assumed here.

## 18. Migration Constraints

**[TARGET STATE]** *(BRD.md §11, PRD.md §11)*
- No automated regression suite exists today to validate against — parity must be established via newly authored tests, not a "ported" suite.
- No frontend changes are permitted as part of this migration.
- No database schema migration is permitted.
- Existing response shapes must be matched exactly unless a frontend change is made in lockstep (which is out of scope).

**[Open Question]** Module 1 material does not specify a migration **strategy** (big-bang cutover vs. parallel-run vs. phased/strangler-fig endpoint-by-endpoint migration), a rollback plan, or a cutover procedure. These are architecture-design decisions not yet made and must not be assumed.

## 19. Risks and Dependencies

**[CURRENT STATE / confirmed, from BRD.md §7 Risk Register]**

| # | Risk/Dependency | Severity | Source |
|---|---|---|---|
| 1 | No test suite exists; migration could introduce undetected regressions in revenue-critical flows | High | `CURRENT_STATE.md` §10 |
| 2 | Deployment target ambiguity could misdirect cutover planning | Medium | `CURRENT_STATE.md` §2 |
| 3 | Confirmed contract gaps (dropped `country`, inconsistent validation shapes) could cause mid-project disagreement if not resolved upfront | Medium | `CURRENT_STATE.md` §4, §9 |
| 4 | Unauthenticated debug endpoints extend unreviewed surface area if carried forward without a decision | Medium | `CURRENT_STATE.md` §3 |
| 5 | Dependency on Stripe, Cloudinary, and Google OAuth continuing to function identically — none of these were runtime-verified during Module 1 (no live credentials available) | Not runtime-verified | `BUSINESS_PROBLEM_STATEMENT.md` §14 item 7 |
| 6 | Dependency on MongoDB connectivity/data integrity being stable for a new Python driver — not runtime-verified | Low (assumed) | `BRD.md` §7 item 6 |

## 20. Assumptions

**[Explicitly labeled Assumptions, carried forward — not re-derived]** *(BUSINESS_PROBLEM_STATEMENT.md §10, BRD.md §10)*

- The FastAPI decision is organizational/skills-driven, not a response to a proven defect.
- MongoDB remains the system of record; no data migration is planned.
- The existing frontend continues unmodified against the new backend.
- Stripe, Cloudinary, and Google remain the payment, media, and identity providers respectively.
- The actual current production hosting platform can and will be confirmed by the system owner before cutover.
- Current MongoDB connectivity, data volume, and integrity are stable — unverified at runtime.

## 21. Open Questions

*(Consolidated from all Module 1 documents plus architecture-specific questions raised while producing this document. All are gated behind Jira Story RFOMS-2, "Confirm and freeze the API contract inventory," except where noted as newly raised here.)*

1. Which platform is the actual current production deployment target — Render/Netlify or Coolify? *(carried)*
2. Should "Business Insights" analytics remain global or become scoped to the logged-in restaurant owner? *(carried)*
3. Should the four unauthenticated debug/test analytics endpoints be ported, secured, or retired? *(carried)*
4. Is the dead `session_id` cookie fallback / unchecked OAuth `state` param intentional to retain, or safe to remove? *(carried)*
5. Should the delivery `country` field finally be persisted? *(carried)*
6. Should the validation-error-shape inconsistency be replicated as-is or unified? *(carried)*
7. Should the non-Stripe-error crash in checkout session creation be replicated or fixed? *(carried)*
8. Should Stripe event types other than `checkout.session.completed` gain handling? *(carried)*
9. Should `ApiDocsPage`'s incorrect endpoint and `ApiStatusPage`'s "Auth0" mislabel be corrected? *(carried)*
10. What automated test coverage level is required before migration is considered complete? *(carried)*
11. Who is the accountable business/product owner for approving deviations from current behavior? *(carried)*
12. **(New)** What async MongoDB driver/ODM will the target backend use? Not specified in PRD.md.
13. **(New)** Will the target backend be containerized following the existing Docker pattern, and on which platform will it run? Contingent on Open Question #1.
14. **(New)** Is any observability tooling (structured logging, metrics, tracing) required for the target state, given the current system has none and none was requested?
15. **(New)** What is the intended migration/cutover strategy — big-bang, parallel-run, or phased (e.g., strangler-fig) — and what is the rollback plan if issues are found post-cutover?
16. **(New)** Are there scalability, performance, or availability targets the business wants to set for the target system, given none exist today and none were requested in Module 1?

---

**Next step:** With this requirements baseline confirmed, Module 2 can proceed to the target architecture design itself (component diagram, technology selections for the open items above, deployment topology) — pending resolution of the open questions that block it, particularly #1 (deployment target) and #12–#16 above.
