# Product Requirements Document (PRD)
## Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Sources:** `CURRENT_STATE.md`, `BUSINESS_PROBLEM_STATEMENT.md`, `BRD.md`. Labels: **Confirmed** (traced to `CURRENT_STATE.md`), **Proposed** (new requirement introduced by this modernization), **Assumption** (unverified, explicitly flagged), **Open Question** (unresolved, needs a decision-maker).

---

## 1. Product Overview

**Today (Confirmed):** BigHungers is a food-ordering platform with a React/TypeScript SPA frontend and a Node.js/Express/TypeScript backend, backed by MongoDB. It supports restaurant browsing and search, cart and checkout via Stripe, order tracking, restaurant-owner menu and order management, and a business analytics dashboard. The backend exposes 22 HTTP endpoints across 6 route groups (`auth`, `my/user`, `my/restaurant`, `restaurant`, `order`, `business-insights`), authenticates via JWT (password login/register and server-side Google OAuth), and integrates with Stripe (payments) and Cloudinary (image upload).

**After modernization (Proposed):** The same product, from the frontend's and end-user's perspective, with the backend reimplemented in Python/FastAPI. The frontend, the MongoDB data store, and all third-party integrations (Stripe, Cloudinary, Google OAuth) remain unchanged. No new user-facing functionality is introduced by this project.

## 2. User Journeys

Each journey below is **Confirmed** from `CURRENT_STATE.md` §1 and must be preserved without frontend change; the listed endpoints are the backend contract each journey depends on.

| # | Journey | Depends on |
|---|---|---|
| 1 | Browse restaurants by city, filter by cuisine, sort, and paginate results. | `GET /api/restaurant/cities/all`, `GET /api/restaurant/search/:city` |
| 2 | View a restaurant's menu and build a cart (held client-side in `sessionStorage`, cleared on leaving the page). | `GET /api/restaurant/:restaurantId` |
| 3 | Check out: confirm delivery details, redirect to Stripe-hosted payment, return to an order-status page on success or the restaurant page on cancellation. | `POST /api/order/checkout/create-checkout-session`, `POST /api/order/checkout/webhook` (Stripe-initiated) |
| 4 | Track an active order's status via polling. | `GET /api/order` |
| 5 | Register or sign in with email/password, or sign in with Google (full-page redirect flow), then land back in the app authenticated. | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/google`, `GET /api/auth/callback/google`, `GET /api/auth/validate-token`, `POST /api/auth/logout` |
| 6 | View and edit personal profile (name, address, city, country). | `GET /api/my/user`, `PUT /api/my/user` |
| 7 | Create or update a restaurant profile and menu (with an image), as a restaurant owner. | `GET /api/my/restaurant`, `POST /api/my/restaurant`, `PUT /api/my/restaurant` |
| 8 | View and update incoming orders for the owned restaurant, including unpaid "placed" orders. | `GET /api/my/restaurant/order`, `PATCH /api/my/restaurant/order/:orderId/status` |
| 9 | View a business analytics dashboard (revenue, top cities/cuisines, monthly trend, recent orders), available whether or not the viewer is logged in. | `GET /api/business-insights`, `GET /api/business-insights/public` |

## 3. Functional Requirements

### 3a. Preserved Functionality (must remain unchanged)

**Authentication (`/api/auth`) — Confirmed, `CURRENT_STATE.md` §3, §5**

| ID | Requirement |
|---|---|
| PF-01 | `GET /google` redirects to Google's OAuth authorization URL. |
| PF-02 | `GET /callback/google` exchanges the authorization code, upserts the user by email, issues a 1-day JWT, and redirects to the frontend with token and profile fields as URL query parameters. |
| PF-03 | `POST /register` validates email/password (≥6 chars)/name, creates a user, and returns a 201 with a JWT. |
| PF-04 | `POST /login` validates credentials via bcrypt comparison and returns a 200 with a JWT. |
| PF-05 | `GET /validate-token` returns `{ userId }` for a valid Bearer token. |
| PF-06 | `POST /logout` clears the (currently unused) `session_id` cookie. |

**User profile (`/api/my/user`) — Confirmed**

| ID | Requirement |
|---|---|
| PF-07 | `GET /` returns the current user by token identity, 404 if not found. |
| PF-08 | `POST /` preserves its current behavior (checks existence, does not create a user) — see BM-list for the naming/behavior mismatch this preserves rather than fixes. |
| PF-09 | `PUT /` validates and overwrites `name`, `addressLine1`, `city`, `country`. |

**Restaurant management, owner (`/api/my/restaurant`) — Confirmed**

| ID | Requirement |
|---|---|
| PF-10 | `GET /order` returns all orders for the caller's restaurant, including unpaid "placed" orders. |
| PF-11 | `PATCH /order/:orderId/status` updates order status only if the caller owns the restaurant that owns the order; rejects with 401 otherwise. |
| PF-12 | `GET /` returns `null` (200) when the caller has no restaurant. |
| PF-13 | `POST /` creates a restaurant (409 if one already exists for the caller), converting submitted decimal prices to integer pence, and uploading the submitted image to Cloudinary. |
| PF-14 | `PUT /` updates the caller's restaurant with the same price-conversion and optional image-replacement behavior. |

**Restaurant discovery, public (`/api/restaurant`) — Confirmed**

| ID | Requirement |
|---|---|
| PF-15 | `GET /cities/all` returns the distinct list of cities with at least one restaurant. |
| PF-16 | `GET /:restaurantId` returns a single restaurant by ID, 400 for a malformed ID, 404 if not found. |
| PF-17 | `GET /search/:city` supports `searchQuery`, `selectedCuisines` (AND semantics via Mongo `$all`), `sortOption` (always ascending), and `page` (fixed page size 10); `city="all"`/empty skips the city filter. |

**Orders & payments (`/api/order`) — Confirmed**

| ID | Requirement |
|---|---|
| PF-18 | `GET /` returns the caller's orders (current filter matches the full status enum, i.e., no exclusion). |
| PF-19 | `POST /checkout/create-checkout-session` creates an unsaved order, computes a pence-based subtotal + delivery price, creates a Stripe Checkout Session, and persists the order only after Stripe returns a session URL. |
| PF-20 | `POST /checkout/webhook` verifies the Stripe signature against the raw request body and, on `checkout.session.completed`, sets the order's `status` to `paid` and `totalAmount` to Stripe's `amount_total`. |

**Business analytics (`/api/business-insights`) — Confirmed**

| ID | Requirement |
|---|---|
| PF-21 | `GET /` returns a global (not per-restaurant) analytics aggregate for an authenticated caller. |
| PF-22 | `GET /public` returns the identical aggregate without authentication. |
| PF-23 | `GET /test`, `GET /db-test`, `GET /debug-orders`, `GET /debug-restaurants` exist unauthenticated today; their disposition in the new backend is an **Open Question** (see §10 and open question 4), not a default carry-forward. |

**Cross-cutting business rules — Confirmed, `CURRENT_STATE.md` §8**

| ID | Requirement |
|---|---|
| PF-24 | All currency values (`Restaurant.deliveryPrice`, `menuItems[].price`, `Order.totalAmount`) are stored as integer pence; conversion from decimal pounds happens at the restaurant create/update API boundary. |
| PF-25 | Restaurant search cuisine filtering uses AND (all selected cuisines must match), not OR. |
| PF-26 | One restaurant per user is enforced at the application layer (existence check before create), not by a database constraint. |
| PF-27 | Order and restaurant data model shapes (`User`, `Restaurant`, `Order`, embedded `MenuItem`) are preserved exactly, including the current absence of a `country` field on `Order.deliveryDetails` and the absence of a persisted per-line-item price on `Order.cartItems`. |

### 3b. Backend-Modernization-Specific Requirements

These exist because of the language/framework change itself — they describe *how* the same behavior must be achieved under FastAPI, not new business behavior.

| ID | Requirement |
|---|---|
| BM-01 | The FastAPI application must expose the same route prefixes and paths (`/api/auth`, `/api/my/user`, `/api/my/restaurant`, `/api/restaurant`, `/api/order`, `/api/business-insights`) with the same HTTP methods — no path renaming. |
| BM-02 | The webhook route must read the raw, unparsed request body for Stripe signature verification; global JSON body parsing must not run ahead of this route (functional equivalent of Express's `express.raw()`-before-`express.json()` ordering). |
| BM-03 | The authentication dependency (equivalent to `verifyToken`) must accept `Authorization: Bearer <token>`; whether to retain or drop the currently-dead cookie fallback is an explicit design decision, not a default (see open question 5). |
| BM-04 | Response and validation-error JSON shapes must either exactly replicate the two current inconsistent shapes (`{errors:[...]}` vs. `{message:[...]}`) per their endpoint of origin, or be intentionally unified — as an explicit, approved decision (see open question 2), not a silent change. |
| BM-05 | Multipart form-data handling for restaurant create/update must accept the same field name (`imageFile`), the same 5MB size limit, and the same form-field encoding the frontend already sends (`cuisines[index]`, `menuItems[index][name]`, `menuItems[index][price]`). |
| BM-06 | The pounds-to-pence money conversion must be reproduced exactly at the same API boundary (restaurant create/update), not moved to the frontend or the database layer. |
| BM-07 | CORS configuration must admit the same allow-listed origins with `credentials: true` and the same allowed methods/headers. |
| BM-08 | The MongoDB access layer (an appropriate async Python driver/ODM) must read and write the existing collections without altering document shape, field names, or types. |
| BM-09 | The health-check endpoints (`/`, `/health`, `/api/health`) must be reproduced; the current uptime-since-process-start behavior may be carried forward as-is or revisited, but is not a required fix. |
| BM-10 | The Cloudinary upload flow (buffer → base64 data URI → upload, storing the returned `.url`) must be reproduced with equivalent Python library calls. |
| BM-11 | An automated test suite must be introduced covering all 22 preserved endpoints and the cross-cutting business rules in §3a — this is a new requirement of the modernization itself, not a preserved behavior, since no test suite exists today. |

## 4. Non-Functional Requirements

| ID | Requirement | Basis |
|---|---|---|
| NFR-01 | An automated test suite must exist covering all 22 endpoints and the confirmed business rules before the migration is considered complete. | Proposed, addressing confirmed zero-coverage gap (`CURRENT_STATE.md` §10). |
| NFR-02 | Whatever resolution is chosen for the validation-error-shape inconsistency (BM-04) must be applied uniformly across the new backend, not reintroduced inconsistently. | Proposed, addressing confirmed inconsistency (`CURRENT_STATE.md` §9). |
| NFR-03 | CORS and credentialed-request behavior must match the current allow-list exactly. | Confirmed requirement, `CURRENT_STATE.md` §2. |
| NFR-04 | No performance targets (latency, throughput, concurrency) are defined by this PRD, since none were confirmed as necessary or requested. | Explicit non-invention per project rules; flagged as an **Open Question** if the business wants to set one. |
| NFR-05 | No new security controls (rate limiting, security headers, input sanitization beyond current validation) are required by this PRD beyond what replicates current authentication and Stripe/webhook signature verification. | Explicit non-invention per project rules; current absence is a `CURRENT_STATE.md` §9 observation, not a claimed incident. |

## 5. API-Facing Requirements

Restated at the requirement level (no implementation code) from `CURRENT_STATE.md` §3:

- **Auth group** (6 endpoints): contract-preserve as listed in PF-01–PF-06.
- **User-profile group** (3 endpoints): contract-preserve as listed in PF-07–PF-09.
- **Restaurant-management group** (5 endpoints): contract-preserve as listed in PF-10–PF-14, including the middleware-order caveat (see BRD risk register — not required to be re-ordered, but ordering must be a conscious choice, not an accident, if changed).
- **Public-restaurant group** (3 endpoints): contract-preserve as listed in PF-15–PF-17.
- **Order/payment group** (3 endpoints): contract-preserve as listed in PF-18–PF-20.
- **Analytics group** (6 endpoints): the authenticated and public analytics endpoints (PF-21, PF-22) are in scope to preserve; the four debug/test endpoints (PF-23) are explicitly flagged as an **Open Question** — they must not be silently ported, silently secured, or silently dropped without a decision.

## 6. Authentication Requirements

- JWT bearer scheme: payload `{ userId }`, 1-day expiry, verified via `Authorization: Bearer <token>` header. **(Confirmed, must preserve.)**
- Password login/registration: bcrypt-hashed passwords (current cost factor 8), email uniqueness enforced. **(Confirmed, must preserve.)**
- Google OAuth: server-side authorization-code exchange, user upsert by email, JWT issuance, redirect to frontend with token in the query string. **(Confirmed, must preserve.)**
- Two confirmed anomalies require an explicit decision rather than a default carry-forward:
  - The `session_id` cookie fallback in the auth dependency and the cookie-clearing `logout` endpoint are currently dead code (nothing sets the cookie). **(Open Question — retain or remove.)**
  - The Google OAuth `state` parameter is generated but never validated, providing no actual CSRF protection today. **(Open Question — retain as-is or implement validation.)**

## 7. Payment Requirements

- Stripe Checkout Sessions are created server-side, in GBP, with line items priced in integer pence and delivery cost passed as a fixed-amount shipping option. **(Confirmed, must preserve.)**
- The order record is only persisted after Stripe successfully returns a session URL. **(Confirmed, must preserve.)**
- Webhook processing must verify the Stripe signature against the **raw** request body and handle `checkout.session.completed` by setting `status = "paid"` and `totalAmount = amount_total`. **(Confirmed, must preserve — see BM-02.)**
- Two confirmed anomalies require an explicit decision:
  - Non-Stripe errors thrown during checkout session creation (e.g., "Restaurant not found") crash the current error handler, which assumes a Stripe-shaped error object. **(Open Question — replicate the crash behavior as-is, or fix it as part of the port.)**
  - Only `checkout.session.completed` is handled; all other Stripe event types are acknowledged with no side effect. **(Confirmed, preserve unless a decision is made to add handling for other event types — which would be new functionality and is out of scope unless separately approved.)**

## 8. Acceptance Criteria

**Authentication**
- AC-AUTH-1: Given valid credentials, when `POST /api/auth/login` is called, then the response is 200 with a JWT and a user object matching the current shape (`id`, `email`, `name`).
- AC-AUTH-2: Given an invalid password, when `POST /api/auth/login` is called, then the response is 400 with an "Invalid Credentials" message.
- AC-AUTH-3: Given a valid Bearer token, when `GET /api/auth/validate-token` is called, then the response is 200 with `{ userId }`.
- AC-AUTH-4: Given a completed Google OAuth code exchange, when the callback route processes it, then the response redirects to the frontend with a JWT and profile fields in the query string, matching current field names.

**Payments**
- AC-PAY-1: Given a valid cart and restaurant, when `POST /checkout/create-checkout-session` is called, then a Stripe Checkout Session is created with a pence-based total matching the current calculation, and the response is `{ url }`.
- AC-PAY-2: Given a Stripe `checkout.session.completed` event with a valid signature, when `POST /checkout/webhook` is called, then the corresponding order's `status` becomes `paid` and `totalAmount` is set from `amount_total`.
- AC-PAY-3: Given an invalid or missing Stripe signature, when the webhook is called, then the request is rejected with a 4xx response and no order is modified.

**Restaurant management**
- AC-REST-1: Given an authenticated user with no existing restaurant, when `POST /api/my/restaurant` is submitted with valid data and an image file, then a restaurant is created with pence-converted prices and a Cloudinary-hosted image URL.
- AC-REST-2: Given an authenticated user who already owns a restaurant, when `POST /api/my/restaurant` is called again, then the response is 409.
- AC-REST-3: Given a restaurant owner updating an order's status, when the order belongs to their restaurant, then the update succeeds; when it does not, then the response is 401.

**Search & discovery**
- AC-SEARCH-1: Given multiple selected cuisines, when `GET /api/restaurant/search/:city` is called, then only restaurants matching all selected cuisines are returned.
- AC-SEARCH-2: Given a `page` parameter, when search is called, then results are paginated at a fixed page size of 10, matching current behavior.

**Analytics**
- AC-ANALYTICS-1: Given no authentication, when `GET /api/business-insights/public` is called, then the response matches the aggregate shape of the authenticated endpoint, unless a scoping change has been explicitly approved (open question 3).

**Testing baseline**
- AC-TEST-1: Given the migration is complete, when the automated test suite is executed, then it exercises all 22 preserved endpoints and the cross-cutting business rules in §3a, establishing a coverage baseline that did not exist in the current system.

## 9. Dependencies

| Dependency | Nature | Current confirmed configuration surface |
|---|---|---|
| MongoDB | Data store | Connection string via `MONGODB_URI`/`MONGODB_CONNECTION_STRING`; existing `User`, `Restaurant`, `Order` collections. |
| Stripe | Payment provider | `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`; GBP-only Checkout Sessions. |
| Cloudinary | Media storage | `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`. |
| Google OAuth | Identity provider | `GOOGLE_ID`, `GOOGLE_SECRET`; server-side authorization-code flow. |
| Frontend application | Fixed contract dependency | Cannot change under this project; all backend contracts must match its current expectations. |
| Deployment platform confirmation | Blocking dependency for cutover planning | **Open Question** — Render/Netlify vs. Coolify (`CURRENT_STATE.md` §2). |

## 10. Out-of-Scope Items

- Any frontend redesign or frontend code change.
- Any database engine migration away from MongoDB.
- New business features not present in the current system.
- Changing the payment provider, file-storage provider, or identity provider.
- Performance optimization not tied to preserving current behavior.
- Silent resolution of open questions (analytics scoping, debug-endpoint disposition, dropped `country` field, validation-shape unification, dead cookie fallback, OAuth `state` validation) — each requires explicit business/product sign-off before implementation, not a default engineering choice.

*(Source: `BUSINESS_PROBLEM_STATEMENT.md` §13, carried forward without modification.)*
