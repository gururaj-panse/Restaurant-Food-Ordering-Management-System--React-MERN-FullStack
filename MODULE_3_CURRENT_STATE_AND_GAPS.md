# Module 3 — Current-State Code Analysis & Architecture-to-Code Gaps
## Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Status:** Analysis only. No files modified, no code written.
**Basis:** Direct inspection of `food-ordering-backend/src/**`, cross-checked against `CURRENT_STATE.md`, `ARCHITECTURE_REQUIREMENTS.md`, `TARGET_ARCHITECTURE.md`, `TARGET_ARCHITECTURE_C4_DIAGRAM.md` (Rev. 2), `TARGET_ERD.md` (Rev. 2), and `MODULE_2_ARCHITECTURE_AND_SOLUTION_DESIGN.md`.
**Working-tree note:** two uncommitted changes exist (`cloudinary` bumped `1.41.3→2.11.0` in `package.json`; Dockerfile `EXPOSE 5000→3000`) — both are already reflected in the approved Module 1/2 analysis, so no prior finding changes. No test files, no Python files, and no new source files exist anywhere in the repository beyond the Module 1/2 `.md` deliverables.

---

## 1. Backend Entry Point

`food-ordering-backend/src/index.ts` — single file, single process. Boot sequence: `mongoose.connect()` → `cloudinary.config()` → Express app created → CORS → `cookie-parser()` → `express.raw()` scoped **only** to `/api/order/checkout/webhook` → `express.json()` globally → health routes (`/`, `/health`, `/api/health`) → 6 route mounts → `app.listen(PORT || 5000)`. No app-factory pattern, no DI container.

## 2. Routes and Controllers

| Route file | Controller | Endpoints | Target module (per C4 Rev. 2) |
|---|---|---|---|
| `routes/auth.ts` | **none — logic lives in the route file itself** | 6 | Authentication Module |
| `routes/MyUserRoute.ts` | `MyUserController.ts` | 3 | User Profile Module |
| `routes/MyRestaurantRoute.ts` | `MyRestaurantController.ts` | 5 | Restaurant & Menu Module |
| `routes/RestaurantRoute.ts` | `RestaurantController.ts` | 3 | Restaurant & Menu Module |
| `routes/OrderRoute.ts` | `OrderController.ts` | 3 | Order & Payment Module |
| `routes/AnalyticsRoute.ts` | `AnalyticsController.ts` | 6 | Analytics Module |

22 endpoints total, matching the confirmed count in every prior document. **The current code's file-level decomposition already matches the approved 5-module target almost exactly** — see §11.

## 3. Services / Business Logic

**There is no service layer.** Every controller is a flat set of exported functions that call Mongoose models directly — no repository, no DTO/mapping layer, no domain objects. Business logic worth noting for a faithful port:

- **Price conversion** (pounds→pence) happens inline in `MyRestaurantController.ts`, applied identically on create and update.
- **Checkout math** (subtotal from cart items + delivery price) happens inline in `OrderController.createCheckoutSession`, with a **second, separate** menu-item lookup for building Stripe line items — the two lookups have different miss-handling behavior (one defaults to 0, one throws).
- **Ownership checks** (restaurant-owner-only order status updates) are inline per-request comparisons, not a reusable authorization function.
- **Analytics aggregation** (growth calculations, top cities/cuisines, monthly buckets) is hand-rolled in `AnalyticsController.ts` using in-memory `Array.reduce`/`filter` over query results, not a MongoDB aggregation pipeline.

## 4. Database Models & Access Layer

Three Mongoose schemas (`models/user.ts`, `models/restaurant.ts`, `models/order.ts`), imported and queried directly by controllers — no repository abstraction to reimplement or preserve. Confirmed structural facts relevant to implementation: `Restaurant.user`, `Order.restaurant`, `Order.user` are `ref`s but **not** `required`; `Restaurant.menuItems[]._id` is explicitly declared; `Order.cartItems[]._id` exists only via Mongoose's default subdocument behavior (not explicitly declared); `Order.deliveryDetails` has no `country` field; `Order.cartItems` has no `price` field. All match `TARGET_ERD.md` exactly — no drift found.

## 5. Authentication / Authorization

`middleware/auth.ts` exports `verifyToken` — reads `Authorization: Bearer <token>`, falls back to a `session_id` cookie that nothing in the app ever sets, verifies via `jsonwebtoken`, attaches `req.userId`. Password hashing is a Mongoose `pre("save")` hook in `models/user.ts` (bcrypt, cost 8). Google OAuth (authorization-code exchange, userinfo fetch, JWT issuance) is implemented with raw `fetch` calls **inside `routes/auth.ts`**, not delegated to a controller or service — this is the one route file with real business logic in it. Authorization beyond authentication is ownership-based, checked inline per-controller; no role field, no centralized policy layer.

## 6. Configuration & Environment Variables

No config module — `process.env.*` is read inline, scattered across `index.ts`, `routes/auth.ts`, and `OrderController.ts`. Confirmed variable set: `MONGODB_URI` (falls back to `MONGODB_CONNECTION_STRING`), `JWT_SECRET_KEY`, `FRONTEND_URL`, `BACKEND_URL`, `GOOGLE_ID`, `GOOGLE_SECRET`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `PORT`. No `.env` validation/schema exists — a missing var fails wherever it's first dereferenced, not at boot.

## 7. External Integrations

- **Google OAuth** — raw `fetch` to Google's token and userinfo endpoints, entirely inside `routes/auth.ts`.
- **Stripe** — official SDK, instantiated once at module load in `OrderController.ts`; Checkout Session creation and raw-body webhook verification both live in that same file.
- **Cloudinary** — SDK v2 (`cloudinary.v2.uploader.upload`), used only in `MyRestaurantController.ts`'s `uploadImage` helper (buffer→base64 data URI).

## 8. Existing Tests

**None.** No `*.test.*`, `*.spec.*`, Jest/Vitest/Mocha config, or `.github/workflows` anywhere in the repository — confirmed again in this pass, unchanged from Module 1. `scripts/create-test-user.ts` is a manual seed script (`ts-node`), not an automated test. **Module 3 starts from a zero-test baseline; there is no legacy suite to port, translate, or use as a behavioral reference.**

## 9. Frontend-to-Backend Dependencies (must not be broken)

- Two HTTP calling conventions in the frontend: Axios (Bearer-token interceptor, authenticated calls) and raw `fetch` (public restaurant/city endpoints) — both must keep working unmodified.
- Exact multipart field encoding for restaurant/menu submission: `imageFile`, `cuisines[n]`, `menuItems[n][name]`, `menuItems[n][price]`.
- Exact response shapes the frontend destructures by field name (`res.data.token`, `res.data.user.email`, `results.pagination.total`, `{cities:[]}`, the `AnalyticsData` shape, etc.).
- 5-second polling (orders) and 30-second polling (analytics) are the frontend's only "live update" mechanism — the backend must serve fresh data on every poll, not assume a push channel exists.
- Google OAuth redirect must land on `/auth/callback` with `token`, `userId`, `email`, `name`, `image` query parameters, exact names.
- Stripe webhook raw-body handling — indirectly a frontend dependency, since the customer-visible order-status transition depends entirely on it succeeding.

## 10. Areas That Must Be Preserved

Endpoint paths/methods/status codes; JWT payload (`{userId}`) and 1-day expiry; Google OAuth flow and redirect contract; raw-body-before-JSON-parsing ordering for the webhook route; CORS allow-list; the three health endpoints; pence-based currency conversion at the restaurant-write boundary; cuisine `$all` (AND) filtering; fixed page size of 10; always-ascending sort; one-restaurant-per-user as an application-level-only guard; the customer order-status filter that currently matches the full enum (effectively unfiltered); global (not per-restaurant) analytics scope; the Cloudinary upload mechanism and lack of old-asset cleanup.

---

## 11. Comparison Against Module 2 Architecture

**Strong alignment, not a redesign.** The approved 5-module target (Authentication, User Profile, Restaurant & Menu, Order & Payment, Analytics — `TARGET_ARCHITECTURE_C4_DIAGRAM.md` Rev. 2) maps almost one-to-one onto the current controller files:

| Target module | Current code |
|---|---|
| Authentication Module | `routes/auth.ts` (logic embedded in the route file, not a controller — see gap below) |
| User Profile Module | `MyUserController.ts` — already its own file |
| Restaurant & Menu Module | `MyRestaurantController.ts` + `RestaurantController.ts` |
| Order & Payment Module | `OrderController.ts` — **order and payment logic are already in the same file today**, directly confirming the review decision to keep them merged in the target rather than split |
| Analytics Module | `AnalyticsController.ts` — already its own file, confirming the review decision to keep it standalone |

This is a genuinely favorable finding: **the FastAPI port can follow the current file boundaries almost directly**, with one structural exception noted below.

## 12. Architecture-to-Code Gaps

Findings that a Module 3 implementer needs, none of which are resolved by this document:

1. **Authentication has no controller to mirror.** Every other target module has a corresponding current controller file; Authentication's logic is embedded directly in `routes/auth.ts`. Standing up an "Authentication Module" in FastAPI means extracting this logic from a route file, not translating an existing controller — a slightly different porting motion than the other four modules.
2. **No service-layer decision exists.** Module 2 never resolved whether the FastAPI port introduces a routers→services→data-access layering (a common FastAPI convention) or replicates the current flat controller-does-everything structure. `ARCHITECTURE_REQUIREMENTS.md` §8 left this explicitly open. This is the single largest open implementation-design decision blocking a consistent Module 3 code structure.
3. **No request/response schema strategy exists.** Current validation is ad hoc `express-validator` chains per route; FastAPI idiomatically wants Pydantic models. Module 2 requires the *contract* (shapes, status codes) to be preserved but never specified how validation should be structured internally — and the known validation-error-shape inconsistency (Open Question #6) still has no decision.
4. **No async MongoDB driver/ODM is chosen** (Open Question #12, still unresolved) — this blocks writing the data-access layer for any module.
5. **No async connection lifecycle exists to preserve** — the current app does a single synchronous-style `mongoose.connect()` at module load with no startup/shutdown hooks; a FastAPI/async-driver implementation will need one, which is new wiring, not a behavior change, so it's in-scope to design in Module 3 without further approval.
6. **The four debug/test analytics endpoints are real, working code today** (`/test`, `/db-test`, `/debug-orders`, `/debug-restaurants` in `AnalyticsRoute.ts`) — their disposition (Open Question #3) must be settled before the Analytics Module can be called complete against the approved architecture, since "port everything" and "port nothing" are both defensible readings until decided.
7. **Minor:** `AnalyticsController.ts` imports the `User` model but the aggregation logic (re-verified in this pass) computes unique customers from `order.user` values directly, never querying the `User` collection — the Analytics Module likely only needs read access to `Order`/`Restaurant`, one narrower than its current literal import list suggests. Worth confirming during implementation rather than copying the import as-is.
8. **Health-endpoint uptime bug is unresolved** (Open Question #20) — the current in-process-closure uptime calculation is known-incorrect under multiple instances, and whether the target deployment runs multiple instances is still undecided, so whether to reproduce or fix this remains open.

No gap above requires a new file to be created or any code to be written — this document is analysis only.
