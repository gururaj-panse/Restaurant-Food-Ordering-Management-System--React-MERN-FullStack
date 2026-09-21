# Architecture & Solution Design
## Module 2 — Final Document
### Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Status:** Final, consolidating reviewed and approved outputs only — `ARCHITECTURE_REQUIREMENTS.md`, `TARGET_ARCHITECTURE.md`, `TARGET_ARCHITECTURE_C4_DIAGRAM.md` (Rev. 2, post-review), `TARGET_ERD.md` (Rev. 2, post-review). No new technology, component, entity, or decision is introduced here. Where current state and target state differ, both are stated explicitly.

---

## 1. Architecture Overview

This modernization replaces the system's Node.js/Express/TypeScript backend with a Python/FastAPI backend. It is a **like-for-like language port**, not a re-platform: the React frontend, the MongoDB database (schema unchanged), and all three external integrations (Google OAuth, Stripe, Cloudinary) are preserved exactly. The organizational driver is stated in Module 1 as skills/ecosystem alignment, explicitly not a response to a proven system defect (`BUSINESS_PROBLEM_STATEMENT.md`). The target architecture keeps the system's existing shape — one frontend deployable, one backend deployable, one database, three external services — and introduces no new infrastructure.

## 2. Current-State Architecture

A single-process monolith: a React SPA calling a Node.js/Express backend directly, which talks to MongoDB and to Google, Stripe, and Cloudinary with no intermediary layers — no API gateway, cache, queue, or background worker. The backend has no service layer (controllers call Mongoose models directly), 22 confirmed HTTP endpoints across 6 route groups, and no automated tests. Two deployment-configuration lineages coexist in the repository (Render/Netlify vs. Coolify) with no confirmation of which is live. *(`CURRENT_STATE.md` §2, §10)*

## 3. Target-State Architecture

The same topology, with the backend re-implemented in FastAPI as five internal logical modules within **one** deployable process — not microservices:

- Authentication Module
- User Profile Module
- Restaurant & Menu Module
- Order & Payment Module
- Analytics Module

This module set was corrected during architecture review: Payment stays merged with Order (they share one controller today, and splitting them was an unjustified structural change); Analytics stands alone (it was briefly and incorrectly merged into Order Management); User Profile has its own module (it was briefly missing). See `TARGET_ARCHITECTURE_C4_DIAGRAM.md` for the full diagram and rationale.

## 4. Major Components

| Component | Responsibility |
|---|---|
| Customer Application | Browse/search restaurants, cart, checkout, order tracking, profile — usable by guests (browsing, public analytics) and signed-in customers |
| Restaurant/Admin Application | Restaurant profile & menu management, incoming order management — a route-gated view-set in the *same* SPA, not a separate app |
| Authentication Module | Issue/validate JWTs, password register/login, drive the Google OAuth exchange |
| User Profile Module | Get/update the authenticated user's own profile |
| Restaurant & Menu Module | Restaurant CRUD (incl. embedded menu items, Cloudinary upload), public discovery/search |
| Order & Payment Module | Order retrieval and status updates, Stripe Checkout session creation, raw-body webhook verification and order confirmation |
| Analytics Module | Global, publicly-readable business analytics aggregation |
| MongoDB | System of record — `User`, `Restaurant` (embedded menu items), `Order` |

## 5. External Integrations

| System | Role | Interaction |
|---|---|---|
| Google OAuth | Identity verification | Backend-side authorization-code exchange + userinfo fetch; the backend still issues and owns its own JWT — Google is not a trusted token authority the backend delegates to |
| Stripe | Payment processing | Backend creates Checkout Sessions; Stripe calls back via a signed webhook over the **raw** request body — the system's only inbound, asynchronous, third-party-initiated call |
| Cloudinary | Image hosting | Backend uploads restaurant images (buffer→base64→upload); no cleanup of replaced images (known gap) |
| robohash.org | Avatar fallback | Called **directly from the browser** — no backend involvement at all |

*(Auth0 is not part of this architecture. It exists only as a stale, unused artifact in `.env.example` and a mislabeled row on `ApiStatusPage.tsx` — confirmed in Module 1 and explicitly excluded by decision when the target architecture was approved.)*

## 6. Key Data Flows

- **User authentication:** password — App → Auth Module → MongoDB → JWT returned. Google — App → Auth Module → Google (exchange) → MongoDB (upsert) → backend-issued JWT via redirect.
- **Restaurant/menu browsing:** App → Restaurant & Menu Module → MongoDB (public, unauthenticated).
- **Order placement (checkout):** App → Order & Payment Module → Stripe (create Checkout Session) → MongoDB (order persisted **only after** Stripe confirms the session) → browser redirected to Stripe.
- **Payment:** Stripe → Order & Payment Module (signed webhook, **raw body read before any JSON parsing**) → MongoDB (`status` → `paid`, `totalAmount` set from Stripe's authoritative value).
- **Order/status updates:** App polls Order & Payment Module every 5 seconds → MongoDB → latest status. **No push mechanism exists or is planned** — this is the system's entire real-time behavior.
- **Image/media handling:** Admin App → Restaurant & Menu Module → Cloudinary (upload) → MongoDB (store returned URL).

## 7. Security Architecture

- **Authentication:** JWT (`{userId}` payload, 1-day expiry, Bearer header), preserved exactly. Password hashing preserved (bcrypt-equivalent).
- **Authorization:** ownership-based, not role-based — no `role` field exists; "restaurant owner" is inferred from a `Restaurant.user` match, re-checked per request. No centralized authorization layer.
- **Payment security:** Stripe webhook authenticity is established solely by signature verification over the raw request body — this is the one point where an external party's input is trusted, and only after verification.
- **Data protection:** the browser is never trusted with any secret beyond its own JWT; the backend is the sole holder of `JWT_SECRET_KEY`, `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `CLOUDINARY_*`, `GOOGLE_SECRET`, and `MONGODB_URI`.
- **Security boundaries:** public (discovery, auth entry points, public analytics, and — unresolved — four debug/test analytics endpoints); JWT-protected (profile, restaurant management, orders); ownership-checked (order status updates); signature-protected (webhook only).
- **No new security controls** (rate limiting, security headers, additional sanitization) are introduced — none were confirmed as required by Module 1, and none are invented here.

## 8. Deployment Architecture

- **Frontend deployable:** static SPA build, unchanged hosting approach (Netlify/Vercel configs both exist in-repo; which is live is unconfirmed).
- **Backend deployable:** one container image, following the existing multi-stage Dockerfile pattern (Node image replaced by a Python/FastAPI image), exposing the same health-check endpoint (`/api/health`) the current `HEALTHCHECK` already targets.
- **Data store:** MongoDB, external to both deployables, reached only by the backend.
- **Not decided by this document:** which platform (Render/Netlify vs. Coolify) is authoritative, and whether the backend will run as multiple instances — both remain open (§13).

## 9. Migration Strategy

Module 1 and Module 2 establish the target shape and contract but **do not define a migration sequencing method** — no big-bang-vs-phased decision, and no rollback plan, exists in any approved document. What *is* established, and can inform that decision later, is a natural incremental order surfaced by the Jira backlog (Epic RFOMS-1):

1. Freeze the API contract (Story RFOMS-2) — resolve the product-level open questions before any code is written.
2. Stand up the FastAPI scaffold, CORS, health checks, and the raw-body webhook exception.
3. Implement the MongoDB data-access layer against the unchanged schema.
4. Implement Authentication, then User Profile (both gate everything downstream).
5. Implement Restaurant & Menu, then public Search/Discovery.
6. Implement Order & Payment (the highest-risk integration point).
7. Implement Restaurant Order Management, then Analytics.
8. Point the unmodified frontend at the new backend and verify every integration point.
9. Regression-test every user journey; establish the test-coverage baseline throughout, not at the end.

This order is a **practical sequencing observation**, not an approved cutover strategy — the actual migration approach (parallel-run, endpoint-by-endpoint strangler pattern, or full cutover) is an open question (§13).

## 10. Architecture Decisions

| Decision | Rationale |
|---|---|
| Single FastAPI process, five internal modules — not microservices | No service-boundary requirement exists anywhere in Module 1; a monolith-to-monolith language port matches the "like-for-like" modernization goal |
| Order and Payment kept in one module | They share one controller today (`OrderController.ts`); splitting them was reviewed and rejected as an unjustified structural change |
| No queue, cache, or orchestration introduced | No async/eventing need beyond the single Stripe webhook; no performance/scale target exists to justify them |
| MongoDB schema unchanged, no migration | Explicit constraint (`BRD.md` §11); confirmed data gaps are flagged, not silently fixed |
| Identity built on JWT + Google OAuth, not Auth0 | Auth0 is not integrated anywhere in the current system; introducing it would be a new-provider scope change requiring separate approval — confirmed by explicit decision |
| Raw-body webhook handling preserved exactly | The single highest-risk integration-ordering requirement in the system; any deviation breaks Stripe signature verification |

## 11. Risks and Trade-offs

| Risk | Mitigation / Trade-off |
|---|---|
| No automated test suite exists to validate parity | A test-coverage baseline is a required deliverable of this project, not an assumed inheritance (`PRD.md` NFR-01) |
| Deployment target is unconfirmed | Must be resolved before cutover planning (`BRD.md` BR-9); this document deliberately stays platform-agnostic until then |
| Stripe webhook idempotency/redelivery-safety was never verified | Treated as an open question, not assumed safe or unsafe |
| Raw-body/JSON-parsing ordering is easy to get wrong in a new framework | Called out explicitly in every architecture document and on the diagram's webhook arrow itself, to keep it visible through implementation |
| Confirmed data gaps (missing `country`, missing per-line price, unindexed owner ref) could be silently "fixed" or silently reproduced by an implementer without a decision | Each is logged individually and gated behind Jira Story RFOMS-2, requiring explicit product sign-off either way |

## 12. Assumptions

*(Only those explicitly identified during the architecture process — none invented here.)*

- The FastAPI decision is organizational/skills-driven, not a response to a proven defect.
- MongoDB remains the system of record; no data migration is planned.
- The existing frontend continues largely unmodified against the new backend — with the caveat that a specific, approved decision (e.g., unifying the validation-error shape) could require a lockstep frontend change; this is not an absolute rule.
- Stripe, Cloudinary, and Google remain the payment, media, and identity providers respectively.
- The actual current production hosting platform can and will be confirmed by the system owner before cutover.
- Current MongoDB connectivity, data volume, and integrity are assumed stable — unverified at runtime, since the application was not executed during Module 1/2 analysis.
- Stripe webhook redelivery is assumed not to cause harmful double-processing under the current single-pass status-overwrite logic — unverified.

## 13. Open Questions

*(Unresolved — require stakeholder/trainer confirmation; none are resolved by this document.)*

1. Which platform is the actual current production deployment target (Render/Netlify vs. Coolify)?
2. Should "Business Insights" analytics remain global or become scoped to the logged-in restaurant owner?
3. Should the four unauthenticated debug/test analytics endpoints be ported, secured, or retired?
4. Is the dead `session_id` cookie fallback / unchecked OAuth `state` param intentional to retain, or safe to remove?
5. Should the delivery `country` field finally be persisted?
6. Should the validation-error-shape inconsistency be replicated as-is or unified?
7. Should the non-Stripe-error crash in checkout session creation be replicated or fixed?
8. Should Stripe event types other than `checkout.session.completed` gain handling?
9. Should `ApiDocsPage`'s incorrect endpoint and `ApiStatusPage`'s "Auth0" mislabel be corrected?
10. What automated test coverage level/threshold is required before migration is considered complete?
11. Who is the accountable business/product owner for approving deviations from current behavior?
12. What async MongoDB driver/ODM will the target backend use?
13. Will the target backend be containerized following the existing Docker pattern, and on which platform will it run?
14. Is any observability tooling (structured logging, metrics, tracing) required for the target state?
15. What is the intended migration/cutover strategy, and what is the rollback plan?
16. Are there scalability, performance, or availability targets the business wants to set?
17. Is there a real ordering/race risk between order-document persistence and webhook delivery that the architecture must guard against?
18. How will production secrets be managed in the target deployment?
19. Is HTTPS/transport-layer security an explicit requirement, or assumed via the (unresolved) hosting platform?
20. Will the target deployment run multiple backend instances/replicas — this affects whether the current uptime-calculation bug is safe to reproduce as-is?
21. Should the three under-constrained references (`Restaurant.user`, `Order.restaurant`, `Order.user`) be made schema-`required` as part of this modernization?

## 14. Architecture Artifacts

- **C4 Container Diagram** — `TARGET_ARCHITECTURE_C4_DIAGRAM.md` (Rev. 2, post-review corrections applied: 5-module backend, Guest actor added, raw-body detail on the webhook arrow). Published artifact: *BigHungers Container Map*.
- **Entity Relationship Diagram** — `TARGET_ERD.md` (Rev. 2, post-review corrections applied: cardinality symbols corrected on three relationships, `ORDER_ITEM._id` confidence downgraded, snapshot-duplication noted on `DELIVERY_DETAILS`). Published artifact: *BigHungers Entity Map*.

Both diagrams and this document are mutually consistent as of this revision — the review findings for both were applied to the source documents and republished before this final document was written, so no known open correction remains unresolved between them.
