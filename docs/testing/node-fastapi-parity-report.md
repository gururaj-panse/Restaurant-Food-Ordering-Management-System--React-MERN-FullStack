# Node.js ↔ FastAPI Behavioral Parity Report — Order Management & Order Lifecycle Module

**Document type:** analysis artifact. Compares actual source code on both sides plus this session's executed test evidence. **No code was modified to produce this report.**

**Endpoints compared:**
1. `GET /api/order` (both backends mount this path identically — see §0)
2. `GET /api/my/restaurant/order`
3. `PATCH /api/my/restaurant/order/:orderId/status`

**Sources read fresh for this report:**
- Node: `food-ordering-backend/src/controllers/OrderController.ts`, `MyRestaurantController.ts`, `middleware/auth.ts`, `middleware/validation.ts`, `models/order.ts`, `models/user.ts`, `routes/OrderRoute.ts`, `routes/MyRestaurantRoute.ts`, `index.ts`
- FastAPI: `app/services/order_service.py`, `app/services/restaurant_service.py`, `app/api/deps.py`, `app/api/routes/order.py`, `app/api/routes/my_restaurant.py`, `app/core/errors.py`, `app/schemas/order.py`
- Test evidence: `test-results/unit-test-results.md` (45/45 passing), `test-results/api-integration-test-results.md` (55/56 passing, 1 documented skip) — both executed in this session against the real FastAPI app

**Important constraint on this report:** no live Node.js server was started in this session. Every Node-side claim below is derived from reading the actual TypeScript source, not from executing it. Where a claim would benefit from runtime confirmation (e.g., exact framework-default error bodies), it is marked **[SOURCE-ONLY — NOT RUNTIME-VERIFIED]** rather than asserted as fact.

---

## 0. Path Discrepancy — Resolved, Not a Parity Issue

Every prior Phase 4 document (going back to `qa-readiness-notes.md`) flagged that the endpoint commonly referred to as `GET /api/my/order` actually lives at `GET /api/order` in the FastAPI code, without confirming whether this was a migration artifact. **Confirmed this pass:** Node's own `index.ts` mounts `orderRoute` at `app.use("/api/order", orderRoute)` — the path has **always** been `/api/order` in the original system too. This is not a migration discrepancy; it is a naming convention used loosely in planning documents from the start. No further action needed.

---

## 1. Endpoint-by-Endpoint Comparison

### 1.1 `GET /api/order`

| Aspect | Node (`OrderController.getMyOrders`) | FastAPI (`OrderService.get_my_orders`) | Verdict |
|---|---|---|---|
| Query | `Order.find({ user: req.userId, status: { $in: [placed,paid,inProgress,outForDelivery,delivered] } })` | `list_by_user`: same 5-value `$in` filter | **Confirmed match** — both filters are the identical no-op (matches every valid status) |
| Population | `.populate("restaurant").populate("user")` | `populate_order()`: fetches full restaurant + user docs | **Confirmed match** |
| Success | `res.json(orders)` → 200 | `mongo_to_jsonable(populated)` → 200 | **Confirmed match** |
| Empty result | `orders` = `[]`, `res.json([])` → 200 | same → 200 | **Confirmed match** |
| Generic error | `catch { res.status(500).json({message:"something went wrong"}) }` — **lowercase "something"** | Only reachable via FastAPI's registered `unhandled_error_handler`: `{"message":"Something went wrong"}` — **capital "Something"** | **Unexpected difference** — see §4.1 |
| Auth | `verifyToken` middleware, applied before the controller | `Depends(get_current_user_id)` | **Confirmed match** — see §2 |

### 1.2 `GET /api/my/restaurant/order`

| Aspect | Node (`MyRestaurantController.getMyRestaurantOrders`) | FastAPI (`RestaurantService.get_my_restaurant_orders`) | Verdict |
|---|---|---|---|
| No restaurant owned | `if (!restaurant) return res.json([])` → 200 `[]` | `if not restaurant: return []` → 200 `[]` | **Confirmed match** — both explicitly short-circuit before ever querying orders |
| Query (restaurant exists) | `Order.find({ restaurant: restaurant._id })` — **no status filter at all** | `list_by_restaurant(restaurant_id)` — **no filter** | **Confirmed match**, independently verified by both source AND this session's executed regression tests (`API-RST-GET-12`, `UT-RST-GET-05`) |
| Population | `.populate("restaurant").populate("user")` | `populate_order()` | **Confirmed match** |
| Generic error | `{"message":"something went wrong"}` (lowercase) | `{"message":"Something went wrong"}` (capital) via generic handler | Same casing note as §1.1 |

### 1.3 `PATCH /api/my/restaurant/order/:orderId/status`

This is the endpoint with substantive divergence. Table below, followed by a dedicated deep-dive in §3 — the case analysis in §3 is materially more precise than what any prior Phase 4 document stated, and **corrects** an imprecise framing carried since `docs/module-3-code-review.md`.

| Aspect | Node (`MyRestaurantController.updateOrderStatus`) | FastAPI (`RestaurantService.update_order_status`) | Verdict |
|---|---|---|---|
| `orderId` format check | `mongoose.Types.ObjectId.isValid(orderId)` → `400 {"message":"Invalid order ID format"}` | `ObjectId.is_valid(order_id)` → `400 {"message":"Invalid order ID format"}` | **Confirmed match — exact string** |
| Order-not-found | `404 {"message":"order not found"}` | `404 {"message":"order not found"}` | **Confirmed match — exact string** |
| Ownership check | `restaurant?.user?._id.toString() !== req.userId` | `str(restaurant.get("user")) != user_id` (with a falsy-guard) | **Major, deliberate divergence — see §3** |
| Ownership-fail response | `res.status(401).send()` — **empty body** | `EmptyBodyAppError` → empty body, 401 | **Confirmed match on shape** (when Node's code actually reaches this line — see §3) |
| Request body validation | **None** — no express-validator chain attached to this route (`MyRestaurantRoute.ts` only applies `validateMyRestaurantRequest` to `POST`/`PUT /`) | `payload: dict` — FastAPI/Pydantic rejects non-object JSON bodies → `400 {"errors":[...]}` before the service runs | **Intentional/incidental FastAPI-only addition — see §4.2** |
| Status enum validation | Mongoose schema `enum` on `Order.status`, enforced at `.save()` time → `500` (via the same generic catch) | Explicit `_ORDER_STATUSES` set membership check → `500 {"message":"unable to update order status"}` | **Confirmed matching intent, but see §3 — Node's version is unreachable in production today** |
| Success response shape | `res.status(200).json(order)` — the **same, local, mutated Mongoose document**, NOT re-populated | `mongo_to_jsonable(updated_order)` — a **fresh re-fetch from the DB**, also not populated | **Confirmed match on "not populated"; differs on re-fetch vs. in-memory — see §4.3** |
| Generic/status-invalid error message | `{"message":"unable to update order status"}` | `{"message":"unable to update order status"}` | **Confirmed match — exact string, but see §3 for why this string means different things on each side** |
| Lifecycle enforcement | None — `order.status = status` unconditionally | None — no current-status check before writing | **Confirmed match in code intent — but only FastAPI can actually demonstrate it today, see §3** |
| `totalAmount` on this write path | Untouched — only `.status` is mutated before `.save()` | Untouched — `update_status(order_id, status=status)` omits `total_amount` | **Confirmed match**, independently verified by this session's `API-RST-PATCH-28` |

---

## 2. Authentication Requirements

| Aspect | Node (`middleware/auth.ts`) | FastAPI (`app/api/deps.py: get_current_user_id`) | Verdict |
|---|---|---|---|
| Token sources | `Authorization: Bearer <token>` header, else `req.cookies["session_id"]` | Identical: `Authorization: Bearer <token>` header, else `session_id` cookie | **Confirmed match** |
| Missing token | `401 {"message":"unauthorized"}` | `401 {"message":"unauthorized"}` | **Confirmed match — exact string** |
| Invalid/expired/wrong-signature token | `jwt.verify()` throws → caught → `401 {"message":"unauthorized"}` (no distinction between failure reasons) | `jwt.decode()` throws → broad `except Exception` → `401 {"message":"unauthorized"}` (same non-distinguishing behavior) | **Confirmed match**, and independently verified live by this session's `API-ORD-GET-04..09` / `API-RST-GET-05..10` / `API-RST-PATCH-09..14` (18 executed auth-failure requests, all passing) |
| JWT claim read | `(decoded as JwtPayload).userId` | `str(payload["userId"])` | **Confirmed match** |
| Algorithm | `jwt.verify(token, JWT_SECRET_KEY)` — `jsonwebtoken` defaults to accepting the algorithm embedded in the token's own header unless restricted | `jwt.decode(token, secret, algorithms=["HS256"])` — **explicitly restricts to HS256** | **Unexpected/beneficial difference — see §4.4** |

**Correction to prior documentation:** `docs/module-3-development-plan.md` §7 lists "whether to retain or drop the dead `session_id` cookie fallback (RFOMS-41)" as an open decision, implying it was unused/dead code in Node. Having now read `middleware/auth.ts` directly, this is **not accurate** — the cookie fallback is live, reachable code on the Node side (`token = req.cookies["session_id"]` when no Bearer header is present), identical in shape to what FastAPI now implements. This should be treated as a **confirmed match**, not an open product question about "dead code." (This does not retroactively resolve RFOMS-41 as a product decision — only the "is it dead code" factual premise.)

---

## 3. Deep-Dive: The Ownership-Check Divergence (Finding C2), Precisely Characterized

Prior documentation (`docs/module-3-code-review.md`, `restaurant_service.py`'s own docstring, `docs/testing/qa-readiness-notes.md`) described this as "Node's ownership check crashes for any restaurant with a `user` set, essentially always." That is directionally correct but imprecise. A full case analysis of the actual line, done fresh for this report, is:

```ts
if (restaurant?.user?._id.toString() !== req.userId) {
  return res.status(401).send();
}
```

`restaurant.user` here is an **unpopulated** Mongoose `ObjectId` reference (this code path never calls `.populate("user")` on the restaurant) — plain `ObjectId` instances have no `_id` property.

| Case | `restaurant?.user?._id` evaluates to | Then `.toString()` | Outcome |
|---|---|---|---|
| Restaurant not found (`restaurant === null`) | `undefined` (first `?.` short-circuits) | on `undefined`... wait — no, the whole `?.` chain short-circuits to `undefined` *without* calling `.toString()` at all when the chain breaks early — only the **final**, non-optional `.toString()` after the last `?.` is at risk | **No crash.** `undefined !== req.userId` → always `true` → **401** |
| Restaurant found, `restaurant.user` is falsy (never assigned) | `undefined` (second `?.` short-circuits) | not reached, same reason | **No crash.** → always **401** |
| Restaurant found, `restaurant.user` is a real `ObjectId` (an assigned owner — the normal, common case) | `restaurant.user._id`, a **plain, non-optional property access on a real object** → `undefined` (ObjectId has no `_id` field, but accessing it doesn't throw) | `.toString()` is called **directly** (no `?.` guards it) on `undefined` → **`TypeError: Cannot read properties of undefined`** | **Crash**, caught by the outer `catch`, → **500 `{"message":"unable to update order status"}`** |

**Exhaustive conclusion:** the `!==` comparison itself is **never actually evaluated** for any real restaurant with an owner — the crash happens while constructing its left-hand side. This means:

- **A legitimate restaurant owner can never successfully update an order's status in Node today.** Every call against a real, owned restaurant crashes to 500, regardless of whether the caller is the rightful owner or a stranger.
- The `401` branch **is** reachable — but only for two atypical states: an orphaned/deleted restaurant reference, or a restaurant that was somehow created without ever having an owner assigned. For those two specific states, Node's `401 {empty body}` behavior is **byte-for-byte identical** to FastAPI's.
- Because the crash happens before `order.status = status` is ever reached, **the status-enum-validation-500 path is also unreachable in Node's production code today** — there is no real-world input that reaches Mongoose's `.save()` for this route. The `"unable to update order status"` message that a caller sees in Node practice is, overwhelmingly, the ownership-check crash — not the invalid-status message it appears to be.

**This refines a real finding, not just restates it.** The earlier framing ("Node crashes on ownership checks") is true but incomplete — it doesn't communicate that Node's **404 and the empty-body-401's two rare sub-cases match FastAPI exactly**, that **FastAPI's fix isn't just "returns 401 instead of 500" but "makes the endpoint functional for the first time"**, and that **the shared `"unable to update order status"` 500 message masks two completely different root causes** depending on which backend produced it.

**FastAPI's fix, restated precisely:** `restaurant_service.py`'s guard (`restaurant.get("user")` truthiness check before comparison, via a plain dict `.get()` rather than an unguarded `._id` chain) sidesteps the crash entirely and lets the intended comparison actually run. This is why a legitimate owner reaches 200 in FastAPI (confirmed live by `API-RST-PATCH-01`/`-18`) — not because FastAPI "changed the security model," but because it fixed a defect that made the original security model non-functional.

---

## 4. Additional Findings From This Fresh Read

### 4.1 Error-message casing inconsistency (new, minor, confirmed)

Node's two GET-endpoint catch-alls use `"something went wrong"` (lowercase). FastAPI's generic unhandled-exception handler (`app/core/errors.py`) uses `"Something went wrong"` (capital S) — this is the ONLY place this exact 500 would ever surface in FastAPI for these two endpoints (both service methods have no explicit try/catch of their own; an unhandled failure falls through to the app-wide handler). A strict string-equality check on this message (e.g., a frontend catching this exact error text) would break. Low severity, but a real, confirmed difference — not previously documented anywhere in this project's Phase 4 artifacts.

### 4.2 FastAPI adds a request-body validation layer Node never had (PATCH endpoint)

`MyRestaurantRoute.ts` attaches `validateMyRestaurantRequest` only to `POST /` and `PUT /` — **not** to `PATCH /order/:orderId/status`. Node's `updateOrderStatus` performs **zero** validation on the request body shape; `req.body.status` is used directly regardless of what was sent (if the body isn't even an object, `.status` is simply `undefined`, which — per §3 — never reaches the enum check anyway, since the ownership crash fires first for any real restaurant).

FastAPI's `payload: dict` type-hint causes automatic Pydantic validation: a non-object JSON body is rejected with `400 {"errors":[...]}` **before the service is ever called** — confirmed live by this session's `API-RST-PATCH-06`/`-07`. This is a real behavioral addition, not present in Node at all. It's arguably a beneficial strengthening, but per this project's "never silently strengthen an unrequested contract" convention, it should be explicitly flagged rather than assumed harmless — a client that was previously sending malformed bodies and (in Node) silently having them ignored/absorbed would now get a hard 400 from FastAPI.

### 4.3 PATCH success response: in-memory object (Node) vs. fresh re-fetch (FastAPI)

Node's success path serializes the **same in-process Mongoose document instance** that was just mutated and saved (`order.status = status; await order.save(); res.json(order)`) — it never re-reads from MongoDB to confirm what's actually stored. FastAPI's equivalent (`restaurant_service.py`) explicitly re-fetches via `self._orders.get_by_id(order_id)` after the write, then serializes that fresh copy. In the ordinary single-request case these produce identical output, but they represent different verification postures: FastAPI's response reflects what's actually persisted (confirmed correct, independent of the write call's own return value), whereas Node's reflects only what the process believes it wrote. This difference has no observed practical impact in this session's testing but is a genuine implementation divergence worth recording under "database operations," as the task explicitly asked to compare.

### 4.4 JWT algorithm restriction (auth, minor security-positive difference)

Node's `jwt.verify(token, secret)` call does not pass an `algorithms` allow-list, meaning `jsonwebtoken`'s default behavior (accepting whatever algorithm the token's own header claims, within the library's supported set) applies. FastAPI's call explicitly pins `algorithms=["HS256"]`. This is a narrower, more defensive posture on the FastAPI side — not requested or flagged in any prior Phase 4 document, and worth noting as an incidental, not-yet-acknowledged hardening introduced during migration.

### 4.5 Mongoose serialization artifacts absent from FastAPI's response

`models/order.ts`'s schema defines no custom `toJSON`/`toObject` transform. Mongoose's default `.toJSON()` behavior (invoked implicitly by `res.json(order)`) includes the internal `__v` version-key field in the serialized output. FastAPI's PATCH response is a plain Motor dict re-fetched via `mongo_to_jsonable()` — Motor has no equivalent version key, so `__v` is simply absent from the FastAPI response. **[SOURCE-ONLY — NOT RUNTIME-VERIFIED]**: this is inferred from Mongoose's documented default behavior and the schema's lack of an explicit `toJSON` override, not confirmed against a live Node response body in this session. If a frontend or test ever asserts on the exact key set of this response, this is a real discrepancy to know about.

### 4.6 Global unhandled-exception safety net exists only in FastAPI

Node's `index.ts` registers no Express error-handling middleware (`app.use((err, req, res, next) => ...)`) anywhere. Every one of the module's controller functions has its own try/catch, so *known* failure modes are handled — but any exception **outside** those try/catch blocks (e.g., inside a Mongoose hook, a middleware, or an unforeseen async path) has no defined behavior in this codebase and would surface as Express's bare default error handling or an unhandled promise rejection, potentially destabilizing the process. FastAPI's `register_exception_handlers()` registers a catch-all `@app.exception_handler(Exception)` that guarantees every request gets *some* clean 500 JSON response, regardless of where the failure originated. This is a genuine, positive resiliency improvement introduced by the migration — not previously stated this plainly in any Phase 4 document.

---

## 5. Confirmed Behavioral Matches

1. Both GET endpoints' status filters are no-ops (matches the full enum / no filter at all, respectively) — confirmed by source on both sides and by this session's executed tests on the FastAPI side.
2. Both GET endpoints fully populate `restaurant` and `user`, including the bcrypt password hash (finding C1) — **confirmed to be an original Node behavior, not something introduced by the migration.**
3. `order_id` format validation: identical message, identical status code (`400 {"message":"Invalid order ID format"}`).
4. Order-not-found: identical message, identical status code (`404 {"message":"order not found"}`).
5. Ownership-failure response **shape** (empty body, 401) is identical — though reachability differs enormously (§3).
6. `totalAmount` is untouched by the status-update write path on both sides.
7. The PATCH success response is **not** populated on either side (both return raw/plain refs, unlike the GET endpoints) — this was an open "needs verification" item in `docs/testing/api-integration-test-plan.md` §6, now resolved as a confirmed match.
8. No lifecycle/state-machine enforcement exists in either codebase's *source* (though only FastAPI can currently demonstrate this at runtime — see §3).
9. Authentication token sources (`Authorization: Bearer`, `session_id` cookie fallback), the unauthenticated/invalid-token response (`401 {"message":"unauthorized"}`), and the JWT claim name (`userId`) are all identical.
10. Both backends compute the response entirely server-side with no client-trusted status transitions or amounts on this write path.

---

## 6. Intentional Modernization Differences

These are differences FastAPI introduces deliberately, already documented in prior Phase 4 artifacts and reaffirmed here with the more precise case analysis from §3:

1. **The ownership-check fix (C2).** FastAPI makes the endpoint functional for legitimate owners for the first time; Node's version cannot succeed for any real, owned restaurant. This is the headline, highest-priority divergence in the module — see §3 for the exhaustive proof.
2. **Explicit `algorithms=["HS256"]` restriction on JWT verification** (§4.4) — narrower than Node's unrestricted `jwt.verify()`.
3. **A global unhandled-exception handler** (§4.6) that Node has no equivalent of.
4. **Request-body shape validation on the PATCH endpoint** (§4.2) that did not exist in Node at all.

---

## 7. Unexpected Differences (newly surfaced by this fresh comparison — not previously documented)

1. **Error-message casing**: `"something went wrong"` (Node) vs. `"Something went wrong"` (FastAPI's generic handler) — §4.1.
2. **Response-construction method** on PATCH success: in-memory mutated object (Node) vs. fresh database re-fetch (FastAPI) — §4.3.
3. **Mongoose `__v` field** likely present in Node's raw JSON responses, absent from FastAPI's — §4.5. **[SOURCE-ONLY — NOT RUNTIME-VERIFIED]**
4. **The shared `"unable to update order status"` 500 message hides two unrelated root causes** depending on which backend produced it (§3) — a diagnosability concern, not just a text-matching one.
5. **FastAPI's request-body validation (§4.2) means malformed PATCH bodies are rejected before reaching the service — Node has no equivalent gate at all**, not just "the same gate implemented differently."

---

## 8. Unresolved Differences Requiring Investigation

These require either a live Node server or further clarification before they can be stated as confirmed fact rather than inference:

1. **Exact response shape for a malformed-JSON PATCH body with no auth token.** This session's FastAPI-side testing (`API-RST-PATCH-22`) confirmed FastAPI returns `400 {"errors":[...]}` in this combined scenario — body-parsing failure wins over the auth failure. Node's `express.json()` is registered globally (before any route-specific `verifyToken` middleware), so the *same ordering* (body-parse-before-auth) plausibly holds structurally on the Node side too — but Node has **no custom error-handling middleware anywhere** in `index.ts`, so a JSON parse error thrown by `express.json()` would fall through to Express's own default error handler, whose exact response body/content-type (JSON vs. HTML stack trace, depending on `NODE_ENV`) was not confirmed by executing the code. **Action:** run this exact request against a live Node instance (with `NODE_ENV` matching production) to confirm the literal response.
2. **The `__v` field and any other Mongoose `toJSON` artifacts** (§4.5) — confirm by inspecting an actual Node HTTP response body, not just the schema source.
3. **CORS configuration parity** — Node's `index.ts` declares an explicit `methods`/`allowedHeaders` allow-list for CORS; this report did not re-verify FastAPI's `app/core/middleware.py` configuration against it, since CORS is a cross-cutting application concern rather than something owned by the Order Management module specifically. Flagged here only so it isn't assumed covered by this report.
4. **Whether Node's Express/body-parser version has any custom JSON error-handling behavior** that differs from stock Express defaults (e.g., via a dependency-injected middleware not visible from `index.ts` alone) — not fully ruled out without running `npm ls` / inspecting `package.json` middleware dependencies in more depth than this pass covered.

---

## 9. Corrections to Earlier Phase 4 Documentation

In the course of this fresh read, two prior claims were found to be imprecise and are corrected here (not retroactively edited in the original documents, per this project's standing rule against silently altering prior artifacts):

1. **`docs/module-3-development-plan.md` §7**'s framing of the `session_id` cookie fallback as "dead code" in Node is incorrect — it is live, reachable code, identical in shape to FastAPI's implementation (§2).
2. **The general framing of finding C2 ("Node crashes on ownership checks")** across `docs/module-3-code-review.md` and `docs/testing/qa-readiness-notes.md` is directionally correct but was stated without the exhaustive case analysis in §3 of this report — specifically, it did not previously establish that (a) Node's 401-empty-body path IS reachable and byte-identical to FastAPI's for two narrow states, (b) the crash makes the status-enum-validation-500 path completely unreachable in Node's production code, and (c) the shared 500 message text masks two unrelated root causes. This report's §3 should be treated as the authoritative characterization going forward.

---

## 10. Summary Table

| Category | Confirmed match | Intentional difference | Unexpected difference | Unresolved |
|---|---|---|---|---|
| Endpoint behavior (GET ×2) | ✅ §1.1–1.2 | — | error-message casing (§4.1) | — |
| Authentication | ✅ §2 | JWT algorithm restriction (§4.4) | — | body-vs-auth precedence exact shape on Node (§8.1) |
| Authorization (PATCH) | ✅ for 2 narrow sub-cases (§3) | C2 fix (§3, §6) | shared 500 message masks 2 root causes (§7.4) | — |
| Request body/params | ✅ order_id format (§1.3) | PATCH body validation gate (§4.2) | — | — |
| Validation | ✅ order_id message (§1.3) | — | status-enum-500 unreachable in Node (§3) | — |
| HTTP status codes | ✅ 400/404 exact (§1.3) | — | — | — |
| Response structure | ✅ population parity (§1.1–1.3) | — | `__v` field, casing (§4.5, §4.1) | `__v` confirmation (§8.2) |
| Error behavior | ✅ message strings mostly match | global exception handler (§4.6) | casing, message-collision (§4.1, §7.4) | malformed-body shape (§8.1) |
| Database operations | ✅ write scope (only `status`) | re-fetch vs. in-memory (§4.3) | — | — |
| Lifecycle rules | ✅ neither enforces one (§1.3) | — | only FastAPI can demonstrate this live (§3) | — |

No code was modified in the course of this analysis.
