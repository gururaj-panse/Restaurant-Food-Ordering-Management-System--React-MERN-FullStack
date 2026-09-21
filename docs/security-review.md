# Security & Quality Review — Order Management & Order Lifecycle Module

**Scope:** the FastAPI implementation added in Jira Batch 6 / Stories RFOMS-11, RFOMS-12, RFOMS-13. Files under review: `app/services/order_service.py`, `app/services/restaurant_service.py` (order-lifecycle methods only), `app/services/stripe_client.py`, `app/api/routes/order.py`, `app/api/deps.py` (touched hunks), `app/core/errors.py` (touched hunks), `app/schemas/common.py` (touched hunk), `app/schemas/order.py` (touched hunk), `requirements.txt` (touched hunk).

**Out of scope:** the Node backend, unrelated FastAPI service stubs, prior-pass repository/config/db-layer code (reviewed previously), all Module 1/2 documents.

**Reviewer stance:** findings are labelled *Confirmed* (verified by reading the code) or *Preserved from Node* (a pre-existing behavior deliberately reproduced under the project's "never silently fix confirmed behavior" rule). No changes have been made; this document is advisory only.

---

## Summary

| Severity | Count |
|---|---|
| Critical | 2 |
| High | 3 |
| Medium | 6 |
| Low | 5 |
| Informational | 6 |

Two of the Critical/High findings are the same defects already flagged in code docstrings during implementation; documenting them formally here so they receive their own priority tickets rather than being folded into the general RFOMS-2 gap backlog.

---

## Critical

### C1 — Bcrypt password hash leaked in `GET /api/order` and `GET /api/my/restaurant/order` responses (Preserved from Node)

- **Location:** `app/services/order_service.py` `populate_order()` (lines 62–80), invoked from `OrderService.get_my_orders` and `RestaurantService.get_my_restaurant_orders`.
- **Issue:** `populate_order()` merges the full `users` document (from `user_repository.get_by_id`) into the order payload. The `User` document has no field-selection filter, so the `password` field (a bcrypt hash) is returned to any authenticated caller who lists orders. Matches Node's current `.populate("user")` behavior exactly — verified against `food-ordering-backend/src/models/user.ts` (no `select: false` on `password`).
- **Impact:** every authenticated user can retrieve their own bcrypt hash; every restaurant owner can retrieve the bcrypt hashes of every customer who has ordered from them. Bcrypt at cost factor 8 (the confirmed current setting) is still crackable offline against weak passwords, and hash disclosure is itself a category of credential exposure regardless of hash strength. Also enables offline password-reuse verification against unrelated services.
- **Recommended fix:** at repository or schema level, project away `password` (and any other sensitive fields, e.g. future MFA secrets) whenever a `User` document is returned via a populated join. Preferred: introduce a `UserRepository.get_public_by_id()` (or a `PublicUser` shape) used by `populate_order()`, keeping the raw `password`-bearing document only for the auth path. **This is a behavior change from the Node baseline** and therefore needs an explicit ticket + release note, not a silent fix.

### C2 — `updateOrderStatus` endpoint is non-functional in production (Preserved from Node → Deliberately fixed here; needs ticketing)

- **Location:** `app/services/restaurant_service.py` `RestaurantService.update_order_status` (lines 68–118); Node source: `food-ordering-backend/src/controllers/MyRestaurantController.ts` line 138.
- **Issue:** Node's ownership check reads `restaurant?.user?._id.toString() !== req.userId`. `restaurant.user` is an unpopulated ObjectId ref on this path, so `.user._id` is `undefined` and the follow-up `.toString()` throws `TypeError`. The generic catch converts every legitimate owner's request into `500 "unable to update order status"`. The 401 branch is unreachable.
- **Impact:** on the Node backend, no restaurant owner can update an order's status through this endpoint — order fulfillment via the admin app is currently broken. On this FastAPI implementation, a plain string comparison is used instead (`str(restaurant["user"]) == user_id`), which restores the endpoint's intended behavior. This deviates from Node but was flagged in the implementation docstring.
- **Recommended fix:** file a new high-priority defect ticket (impact: production admin-app feature does not work) documenting both the Node defect and this deliberate deviation. Add an integration test asserting the 401 vs. 200 branches both resolve correctly. Add a regression test on the Node side (or a migration note) so cutover verification catches any customer-visible behavior change.

---

## High

### H1 — Unbounded input on `POST /api/order/checkout/create-checkout-session` (Preserved from Node)

- **Location:** `app/api/routes/order.py` line 43 (`payload: dict`); `app/services/order_service.py` `create_checkout_session` (lines 108–186).
- **Issue:** the route body is an unconstrained `dict`. `cartItems` has no maximum length, `quantity` values are cast with `int()` and have no upper bound, `deliveryDetails` fields have no length caps, `restaurantId` is not shape-validated before being handed to `RestaurantRepository.get_by_id`. A caller can submit a cart with 100,000 line items, or a quantity of `2**60`, and drive DB inserts + Stripe API calls with no throttle. `int(cart_item.get("quantity", 0))` raises `ValueError` on non-numeric input and propagates to the generic `Exception` handler as a 500 "Something went wrong."
- **Impact:** DoS surface (memory/CPU on the API host, request-quota exhaustion at Stripe, MongoDB document-size limits reachable on `Order.cartItems`). Confusing error UX. Confirmed to be preserved from Node's own lack of `express-validator` chain on this route.
- **Recommended fix:** as an authenticated-only endpoint, safe input caps are cheap: max 100 line items, quantity in `[1, 1000]`, string field length caps, `restaurantId` must satisfy `ObjectId.is_valid`. `CheckoutSessionRequest` already exists in `app/schemas/order.py` — flip the route body from `dict` to that schema and add explicit `Field(..., max_length=...)` constraints. Contract change vs. Node; open a ticket under RFOMS-2 so the tightening is intentional, not incidental.

### H2 — Stripe SDK global-state key mutation on every call

- **Location:** `app/services/stripe_client.py` `create_checkout_session` line 31 and `construct_event` line 54.
- **Issue:** `stripe.api_key = self._api_key` sets a module-global on the `stripe` package every request. If multiple `StripeClient` instances existed with different keys (multi-tenant, testing side-by-side), the last-writer wins, silently affecting other concurrent requests. `construct_event` does not require `api_key` at all — setting it there is unnecessary noise.
- **Impact:** low current impact (single Stripe account, single client instance). Latent correctness hazard for future multi-tenant or test-parallelization scenarios.
- **Recommended fix:** set `stripe.api_key` once at process start (e.g. in a startup event), or use `stripe.checkout.Session.create(..., api_key=self._api_key)` per-call (explicit parameter, no global mutation). Remove the `stripe.api_key = ...` line from `construct_event` entirely.

### H3 — Non-ObjectId `user_id` silently stored as raw string on the Order document

- **Location:** `app/services/order_service.py` `create_checkout_session` line 162: `"user": ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id`.
- **Issue:** when the (future) JWT dependency returns a `user_id` that is not a valid ObjectId, the fallback stores the raw string on `Order.user`. Node/Mongoose would either cast it via the schema's `ObjectId` type or reject the save entirely. The consequence is a data-consistency drift: some `Order.user` values are `ObjectId`, some are strings; `populate_order()`'s `str(user_ref)` normalization masks this on read, but any consumer using `$lookup`/aggregation against `users._id` (an `ObjectId`) will silently return zero results for the string-typed rows.
- **Impact:** correctness bug for analytics/joins; silent data corruption post-cutover; hard to detect because reads still work.
- **Recommended fix:** either (a) require `ObjectId.is_valid(user_id)` at the boundary and raise 401 if not (once RFOMS-7 lands, the JWT payload's `userId` should always satisfy this), or (b) mirror Mongoose's behavior by throwing a clean `AppError` on cast failure. Do not persist a raw string as a ref.

---

## Medium

### M1 — Hardcoded production hostnames in the CORS allow-list (Preserved from Node)

- **Location:** `app/config.py` `Settings.cors_allow_origins` — includes `"https://mern-food-ordering.netlify.app"` and `"https://mern-food-ordering-hnql.onrender.com"` as literal strings.
- **Issue:** deployment-specific URLs are baked into source. These are not credentials, but they are environment-specific and should not travel with the code across environments (a staging deployment inherits the production CORS grant with no config change).
- **Impact:** low security impact (both hosts belong to the project). Higher operational-hygiene impact: a fork or a repo mirror inherits allow-listed origins that no longer belong to it.
- **Recommended fix:** drive the full allow-list from `FRONTEND_URL` (+ optional `EXTRA_ALLOWED_ORIGINS` env var) rather than a fixed literal list. Preserve the current three as environment defaults in `.env.example`, not in `config.py`.

### M2 — CORS `allow_credentials=True` with a broad allow-list

- **Location:** `app/core/middleware.py` `register_middleware`, and `app/config.py` `cors_allow_origins`.
- **Issue:** `allow_credentials=True` + a multi-origin allow-list means cookies (`session_id` fallback path, per the Node auth middleware) are sent cross-origin from any allow-listed frontend. Combined with H1 (unvalidated checkout endpoint) and the future JWT-in-cookie path, this widens the CSRF surface for state-changing endpoints. Node has the same setting today.
- **Impact:** the `POST /api/order/checkout/create-checkout-session` and `PATCH /api/my/restaurant/order/{id}/status` endpoints are exploitable via CSRF from any allow-listed origin if the caller relies on cookie auth. Bearer-token callers are unaffected.
- **Recommended fix:** once RFOMS-7 lands, decide whether cookie auth is still supported. If yes, add CSRF protection (double-submit token) to POST/PATCH endpoints. If no, drop the cookie-fallback path entirely. This is an Open Question already logged; add a note pointing to it here.

### M3 — Verbose error messages returned to unauthenticated / malformed callers

- **Location:** `app/services/order_service.py` line 133 (`f"Menu item not found: {menu_item_id}"`), line 116 (`"Restaurant not found"`); `app/core/errors.py` line 88–91 (validation error handler dumps `exc.errors()` including field paths and submitted input snippets).
- **Issue:** error messages echo caller-supplied IDs and internal field paths. Low sensitivity (the caller supplied the ID) but useful to an attacker probing for valid record IDs / schema shape.
- **Impact:** slight information leakage; standard practice is to return generic messages for bad-input paths.
- **Recommended fix:** consider generic messages ("Invalid checkout request", "Order lookup failed") for the caller and detailed messages only in logs. Deferred pending the RFOMS-2 decision on the target validation-error contract (Open Question #6).

### M4 — No request-body size cap on the Stripe webhook route

- **Location:** `app/api/routes/order.py` `stripe_webhook` line 50; `raw_body = await request.body()` line 56.
- **Issue:** the webhook is unauthenticated (correct — Stripe signs it). An attacker can POST an arbitrary-sized body to `/api/order/checkout/webhook`; FastAPI will buffer the whole body into memory before signature verification runs, since `construct_event` needs the full payload.
- **Impact:** memory-based DoS. Signature verification does reject the request eventually, but the buffering happens first.
- **Recommended fix:** apply a body-size limit (e.g. 1 MB — well above any real Stripe webhook) via a middleware or reverse-proxy config on the webhook route specifically. Stripe's own docs suggest ≤ 512 KB.

### M5 — Stripe SDK network calls have no explicit timeout

- **Location:** `app/services/stripe_client.py` `create_checkout_session` line 32.
- **Issue:** `stripe.checkout.Session.create(...)` uses the SDK's default connect/read timeout (currently 80 s). A slow Stripe response holds the request handler open; combined with a modest request-rate this reduces server capacity.
- **Impact:** availability/tail-latency under Stripe degradation.
- **Recommended fix:** pass `stripe.max_network_retries` and configure an explicit timeout (e.g. `stripe.default_http_client = stripe.http_client.RequestsClient(timeout=10)` or per-call kwarg where supported).

### M6 — Verbose Stripe error messages forwarded verbatim as plain-text webhook response (Preserved from Node)

- **Location:** `app/services/order_service.py` `handle_stripe_webhook` line 196: `raise WebhookSignatureError(f"Webhook error: {exc}")`.
- **Issue:** the raw `stripe.error.SignatureVerificationError` message is echoed to the caller. Stripe error messages generally contain signature-comparison detail (received vs. expected timestamps, tolerance windows) that helps a legitimate operator debug but also helps an attacker refine forged headers.
- **Impact:** modest — signature verification is still cryptographic; leaked hints don't defeat it. But there's no operational reason to echo Stripe's internal error text to the caller (Stripe itself receives the 400 status; the plain-text body is not consumed by Stripe).
- **Recommended fix:** return a fixed `"Webhook error"` body; keep the detailed `exc` in logs only. Node currently echoes the full message — flag under RFOMS-2 as a deliberate divergence.

---

## Low

### L1 — No security-focused tests for the Order module

- **Location:** `tests/` — `test_repositories.py` covers repository CRUD; nothing exercises auth failure, invalid Stripe signature, tampered totals, ownership rejection, unauthenticated webhook, or password-hash exposure.
- **Impact:** regressions in any of the above would not be caught by CI.
- **Recommended fix:** add `tests/test_order_security.py` covering, at minimum: (a) invalid webhook signature → 400 plain-text; (b) `checkout.session.completed` for a non-existent order → 404; (c) `update_order_status` by non-owner → 401 empty body; (d) `update_order_status` with invalid ObjectId → 400; (e) `get_my_orders` response asserts on the presence of `user.password` (documents the current, intentional leak per C1 so a fix later trips the test intentionally).

### L2 — Stripe webhook route is idempotency-unsafe

- **Location:** `app/services/order_service.py` `handle_stripe_webhook` lines 190–217.
- **Issue:** Stripe retries webhooks with the same `event.id`. The current code will re-`update_status` and re-set `totalAmount` on every retry. This is idempotent for the paid transition (same values), but any future non-idempotent side effect (email, notification, ledger write) added inside this branch will fire multiple times.
- **Impact:** none today; forward-compatibility concern.
- **Recommended fix:** either persist processed `event.id` values in a small collection and short-circuit repeats, or gate state transitions with a `find_one_and_update({_id, status: "placed"}, {$set: ...})` so a second attempt no-ops.

### L3 — Ownership check performs one DB read per request even when authorization would fail

- **Location:** `app/services/restaurant_service.py` `update_order_status` lines 101–108.
- **Issue:** `get_by_id(order_id)` is always called before the ownership check, meaning any authenticated user can probe for the existence of an order (the 404 vs. 401 distinction is observable).
- **Impact:** minor enumeration oracle for order IDs. Low value target given order IDs are 24-char random ObjectIds.
- **Recommended fix:** return a fixed 404 for both "not found" and "not owned by caller" branches. Log the distinction server-side. Deferred; document in RFOMS-2.

### L4 — `JWT_SECRET_KEY` defaults to an empty string in `Settings`

- **Location:** `app/config.py` line 25: `JWT_SECRET_KEY: str = ""`.
- **Issue:** an empty default lets the app boot without an explicit JWT secret. Once RFOMS-7 lands, an unset secret would produce trivially-forgeable tokens.
- **Impact:** currently harmless (auth path is a 501 stub). Time bomb for the JWT migration.
- **Recommended fix:** change the type to `str | None = None`, and add a startup-time validation in the auth dependency that raises `RuntimeError` if it is unset, matching the pattern already established in `MongoDB._require_database()`.

### L5 — `create_checkout_session` creates the Order row *before* Stripe session creation

- **Location:** `app/services/order_service.py` lines 160–177: `orders.create(order_document)` on line 168 precedes the `stripe_client.create_checkout_session` call on line 171.
- **Issue:** if the Stripe API fails, the freshly-inserted Order sits in `status: "placed"` with no corresponding checkout session, indefinitely. Matches Node's behavior. Not a security issue per se, but creates orphan records that show up in `getMyOrders` (which returns all statuses including `placed`).
- **Impact:** UX / data-hygiene; not exploitable.
- **Recommended fix:** either delete the Order on Stripe-side failure (compensating action), or create the Stripe session first and only persist the Order on success. Latter is preferable but is a Node-behavior deviation; defer to RFOMS-2.

---

## Informational

### I1 — Environment handling is well-scoped

- `pydantic-settings` loads from `.env`; `.env.example` is committed and `.env` itself is git-ignored (verified in a prior pass). No hardcoded secrets in the reviewed files. `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `FRONTEND_URL` all flow through `Settings`.

### I2 — `stripe.error.StripeError` is an internal module path

- `app/services/stripe_client.py` line 14 aliases `stripe.error.StripeError`. In stripe-python ≥ 7 this is stable, but the public re-export is `stripe.StripeError`. Prefer the public name for forward compatibility.

### I3 — `mongo_to_jsonable` does not handle `Decimal128`, `bytes`, `Binary`, or custom BSON types

- Not a defect for the current schema (all numeric fields are ints, no binary blobs), but worth a docstring line noting the coverage limit so future schema additions don't silently produce serializer errors.

### I4 — `PlainTextAppError` / `EmptyBodyAppError` handler ordering depends on FastAPI's most-specific-class lookup

- `register_exception_handlers` registers the subclass handlers before the base — verified to work under Starlette's current ordering rules. A change in Starlette's handler-resolution semantics could regress this to using the generic `AppError` handler. A unit test asserting webhook 400 body is plain text (not JSON) would document/pin this contract.

### I5 — `get_stripe_client` constructs a fresh `StripeClient` per request

- Trivial cost (two attribute assignments), no cache. Could be memoized with `lru_cache` once `Settings` is resolved as a singleton; not worth doing until measured.

### I6 — Sensitive-data logging audit

- `logger.warning("Stripe webhook signature verification failed: %s", exc)` (line 195) — the exception's `str()` in stripe-python does not include the header value or secret, verified against the SDK. Safe.
- `logger.error("Stripe session creation failed for order %s: %s", order_id, exc)` (line 179) — order ID is not sensitive; exception message may include Stripe error code/message, no keys.
- `logger.error("Invalid orderId in Stripe webhook: %r", order_id)` (line 205) — order ID from webhook metadata, safe.
- No log statement in the reviewed files emits `password`, JWT, cookie, or full request body.

---

## Module 2 Architecture Compliance

Verified against `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md`, `TARGET_ARCHITECTURE_C4_DIAGRAM.md` (Rev. 2), `TARGET_ERD.md` (Rev. 2), and `docs/module-3-development-plan.md`:

| Decision | Status |
|---|---|
| Order & Payment kept as one module (`orderMod`) | ✔ single service class, single router prefix |
| Router → Service → Repository layering | ✔ enforced; no repository imports from routes, no route imports from repositories |
| Motor async driver (not Beanie) | ✔ all DB access via existing repositories |
| Stripe webhook raw-body handling | ✔ `await request.body()` in route, no JSON parsing middleware ahead of it |
| No new infrastructure (Kafka, Redis, K8s, cloud-specific services) | ✔ |
| No Auth0 | ✔ (auth dependency still a stub pending RFOMS-7) |
| Preserve Node business behaviors, flag deviations | ✔ two deviations flagged in-code (C2 above, and the `error.raw.message` crash-bug non-repro) |
| Server-side pricing (never trust client cart totals) | ✔ preserved |
| Same environment variables as Node backend | ✔ no new env keys added; `stripe` package is new but reads `STRIPE_API_KEY` / `STRIPE_WEBHOOK_SECRET` already declared |
| Pydantic schemas for validation | Partial — `CheckoutSessionRequest` is declared but *not* attached to the route (see H1); this preserves Node's unvalidated contract deliberately |

No architectural violations found. The one partial (schema-declared-but-not-wired-into-route) is a deliberate behavior-preservation choice, not a compliance gap.

---

## Recommended Ticketing

1. **New (P1/security):** C1 — filter `password` from populated `User` documents in order responses.
2. **New (P1/defect):** C2 — track the Node ownership-check TypeError and this FastAPI deviation; add regression tests before cutover.
3. **New (P2/hardening):** H1 — bounded input on `create-checkout-session`; wire `CheckoutSessionRequest` schema to the route.
4. **New (P3/correctness):** H2, H3, M4, M5, L2, L4 — batch under a "webhook & Stripe hardening" story.
5. **Add to existing RFOMS-2:** M1, M2, M3, M6, L3, L5 — behavior-preservation decisions blocked on the Node-vs-target contract confirmation.
6. **New (test coverage):** L1 — order-module security test suite.

---

*This review makes no code changes. It documents findings for prioritization ahead of the next implementation batch.*
