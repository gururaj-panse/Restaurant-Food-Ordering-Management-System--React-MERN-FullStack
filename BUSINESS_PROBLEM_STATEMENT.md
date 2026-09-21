# Business Problem Statement — Restaurant Food Ordering Management System Modernization

**Basis:** `CURRENT_STATE.md` (repository current-state analysis, reviewed and approved) and direct repository inspection.

**Reviewed and verified.**

---

## 1. Business Context

BigHungers is an operating restaurant food-ordering platform built on the MERN stack. **(Confirmed)** The system supports customer browsing and ordering, Stripe-based payment, restaurant-owner menu/order management, and a business analytics dashboard, delivered through a React/TypeScript frontend and a Node.js/Express/TypeScript backend backed by MongoDB. The organization has decided to standardize backend implementation on Python/FastAPI. **(Assumption — this decision is an external input to the project; it is not derived from a defect identified in the codebase.)**

## 2. Current Situation

**(Confirmed, from `CURRENT_STATE.md`)**

- Backend: single-entry-point Express/TypeScript app (`src/index.ts`), 22 HTTP endpoints across 6 route files and 5 controllers, no service layer.
- Data: 3 MongoDB collections (`User`, `Restaurant`, `Order`) accessed via Mongoose, no schema-level role/permission model.
- Auth: JWT bearer tokens (1-day expiry) plus a server-side Google OAuth flow; no refresh tokens or revocation.
- Payments: server-side Stripe Checkout Sessions with webhook-based confirmation.
- Media: Cloudinary used for restaurant image upload only.
- Quality tooling: no automated test suite and no CI pipeline exist in the repository.
- Deployment: two sets of deployment configuration/comments coexist (Render/Netlify-oriented CORS entries and code comments vs. a Coolify-oriented `Dockerfile`) — which one reflects the current live environment is unresolved.

## 3. Affected Users

- **Customers** — browse restaurants, place and pay for orders, track order status.
- **Restaurant owners/managers** — manage their restaurant profile and menu, view and update incoming orders.
- **Business/platform stakeholders** — consume the analytics dashboard (currently global across all restaurants, not owner-scoped — **Confirmed**).
- **Engineering team** — builds and maintains the backend; currently absorbs the cost of a codebase with no automated regression safety net.

## 4. Business Pain Points

Presented as confirmed facts or explicitly labeled assumptions — none framed as the system being "broken":

- **(Confirmed)** No automated tests and no CI exist, so there is currently no mechanized way to verify that a change — including this migration — preserves existing behavior.
- **(Confirmed)** Two inconsistent JSON error-response shapes exist across endpoints depending on which validation path is hit, and the codebase contains some frontend/backend contract gaps (e.g., a delivery `country` value collected by the frontend that is never persisted by the current `Order` schema).
- **(Confirmed)** Deployment configuration in the repository points at two different hosting lineages at once, creating ambiguity about the true current production topology.
- **(Confirmed)** Several analytics endpoints (`/test`, `/db-test`, `/debug-orders`, `/debug-restaurants`) exist without authentication; this is a codebase-hygiene observation from the current inventory, not a claim of an active exploit or incident.
- **(Assumption)** Maintaining backend logic in a technology stack outside the target skill set/ecosystem is expected to carry a higher long-term maintenance cost, which is presumed to be a driver for this initiative.

*No performance problems and no security incidents have been identified in this codebase, and none are claimed here.*

## 5. Problem Statement

The organization needs to replace the current Node.js/Express/TypeScript backend with a Python/FastAPI implementation while preserving the existing React frontend, MongoDB data store, JWT/Google-OAuth authentication, Stripe payment and webhook processing, Cloudinary media handling, and all confirmed current business workflows and rules — without an existing automated regression suite to validate parity, and with some unresolved ambiguity (current deployment topology) and a small number of confirmed frontend/backend contract inconsistencies that must be either deliberately preserved or consciously resolved as part of this project, rather than silently changed.

## 6. Business Impact

- **(Confirmed risk)** Absence of an existing test suite means behavioral regressions during the rewrite could go undetected unless new tests are authored as part of this project.
- **(Reasonable business framing)** The checkout/payment flow is revenue-critical; preserving its exact behavior (webhook raw-body verification, currency handling, order status transitions) carries the highest business consequence if disrupted.
- **(Confirmed risk)** Cutover/deployment planning cannot be finalized responsibly until the actual production hosting target is confirmed.
- **(Assumption)** A successful migration is expected to reduce future maintenance friction by consolidating backend development on one stack, though this benefit is not measurable from the codebase alone.

## 7. Modernization Objectives

1. Reimplement all 22 confirmed API endpoints in FastAPI with matching request/response contracts.
2. Preserve MongoDB as the system of record, including the existing `User`, `Restaurant`, and `Order` schema shapes, without a database migration.
3. Preserve JWT-based authentication (`{userId}` payload, 1-day expiry, Bearer header) and the existing server-side Google OAuth flow.
4. Preserve Stripe Checkout Session creation and webhook signature verification, including the raw-body handling requirement.
5. Preserve Cloudinary-based restaurant image upload behavior.
6. Preserve all confirmed current business rules (integer-pence currency handling, cuisine `$all` filter, ownership checks, etc.) unless a deviation is explicitly approved by the business/product owner.
7. Make no changes to the existing frontend application.

## 8. Expected Benefits

*(All items below are assumptions/anticipated outcomes, not proven facts — labeled accordingly.)*

- **(Assumption)** A single backend technology stack aligned with the target team's skills and ecosystem, easing long-term maintenance.
- **(Assumption)** Opportunity to introduce automated test coverage during the rewrite, addressing the confirmed current gap.
- **(Assumption)** Opportunity to resolve confirmed inconsistencies (validation error shapes, deployment ambiguity) through a deliberate, reviewed decision process rather than ad hoc drift.
- **(Assumption)** FastAPI's typed request/response models and automatic OpenAPI schema generation may improve API documentation consistency going forward.

## 9. Success Metrics

- 100% of the 22 confirmed endpoints reimplemented with functionally equivalent request/response contracts (validated against the `CURRENT_STATE.md` API inventory).
- Zero required frontend code changes to operate against the new backend, unless a change is explicitly approved.
- All confirmed workflows (search, checkout/payment, order tracking, restaurant management, analytics) verified functionally equivalent post-migration.
- A defined, non-zero automated test coverage baseline established for the new backend (starting point: 0% today, confirmed).
- No data loss and no required schema migration for existing MongoDB collections.
- Stripe webhook signature verification continues to succeed against the existing `STRIPE_WEBHOOK_SECRET` configuration.

## 10. Assumptions

- The decision to standardize on Python/FastAPI is an external business/organizational decision, not a response to a proven defect in the current system.
- The current MongoDB database and its data remain the system of record; no change of database engine is planned.
- The existing frontend will continue to be used unmodified against the new backend.
- Stripe, Cloudinary, and Google remain the payment, media, and identity providers respectively.
- The actual current production hosting platform can and will be confirmed by the system owner before cutover planning.

## 11. Constraints

- Raw-body Stripe webhook signature verification ordering must be preserved.
- Integer-pence currency representation must be preserved across `Restaurant`/`Order` fields.
- JWT payload shape and 1-day expiry must be preserved, since the existing frontend depends on them unchanged.
- CORS origin/credentials configuration must continue to admit the existing frontend origins.
- Existing JSON response shapes consumed directly by frontend code must be matched exactly unless the frontend is updated in lockstep (explicitly out of scope here).
- No automated regression suite currently exists; parity must be validated through newly authored tests, not a ported suite.
- No frontend changes are permitted under this project.
- No database engine change is planned; none has been justified by the current findings.

## 12. In-Scope Items

- Full backend reimplementation in FastAPI covering all confirmed routes/controllers: auth, my/user, my/restaurant, restaurant, order, business-insights.
- Equivalent data access to the existing MongoDB collections (`User`, `Restaurant`, `Order`).
- Equivalent JWT authentication middleware and server-side Google OAuth flow.
- Equivalent Stripe Checkout session creation and webhook handling.
- Equivalent Cloudinary image upload behavior.
- Preservation of all confirmed current business rules and known quirks, unless a specific deviation is explicitly approved by the business/product owner.
- Introduction of automated tests for the new backend sufficient to validate behavioral parity.

## 13. Out-of-Scope Items

- Any frontend redesign or frontend code changes.
- Any database engine migration away from MongoDB.
- Silent resolution of open product questions (e.g., analytics scoping, fate of debug endpoints) — these require explicit business/product sign-off, not a default choice made during the port.
- Introduction of new features not present in the current system.
- Changing the payment provider, file-storage provider, or identity provider.
- Performance optimization unrelated to preserving current behavior — no performance problems have been confirmed in the current system.

## 14. Open Questions

1. Which platform is the actual current production deployment target — the Render/Netlify pairing implied by CORS/comments, or the Coolify setup implied by the Dockerfile?
2. Should confirmed frontend/backend contract gaps (dropped delivery `country`, inconsistent validation error shapes) be replicated as-is, or corrected as part of this project?
3. Should "Business Insights" analytics remain global, or become scoped to the logged-in restaurant owner?
4. Should the currently-unauthenticated debug/test analytics endpoints be ported, secured, or retired?
5. Is the dead `session_id` cookie / cookie-fallback logic in `verifyToken` intentional legacy support to retain, or safe to drop?
6. What automated test coverage level is required before this migration is considered complete?
7. Who is the accountable business/product owner for approving any deviation from current confirmed behavior during the port?
