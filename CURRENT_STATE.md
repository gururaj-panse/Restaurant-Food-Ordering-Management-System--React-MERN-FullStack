# Current-State Analysis — BigHungers Food Ordering System

**Scope:** Code-level inventory of `food-ordering-backend` (Node.js / Express / TypeScript / Mongoose) and its contract with `food-ordering-frontend` (React / Vite / TypeScript), prepared as the baseline for a modernization from Node/Express to Python/FastAPI.

**Method:** Static reading of source code only. The application was **not** started or exercised during this analysis.

**Prepared:** 2026-09-06 · No application source files were modified to produce this document.

## Confidence legend

| Tag | Meaning |
|---|---|
| **Confirmed** | Directly traced in source code — a schema field, a route handler, a conditional branch. Cited by file path. |
| **Observed** | Seen while running the application. **None in this document** — the app was not executed for this analysis. |
| **Needs confirmation** | Depends on live data, an external service's actual behavior, or a product decision the code alone can't settle. |

---

## 1. Frontend structure & user-facing workflows

**Stack** (Confirmed): Vite + React 18 + TypeScript SPA, `react-router-dom` v6, `react-query` v3 (not v4/v5) for server-state caching, `react-hook-form` + `zod` for forms, Axios for most HTTP calls.

Key files:
- `food-ordering-frontend/src/AppRoutes.tsx` — route table
- `food-ordering-frontend/src/lib/api-client.ts` — shared Axios instance (`baseURL` from `VITE_API_BASE_URL`, `withCredentials: true`, bearer-token request interceptor reading `localStorage.session_id`)
- `food-ordering-frontend/src/contexts/AppContext.tsx` — global `isLoggedIn` state
- `food-ordering-frontend/src/auth/ProtectedRoute.tsx` — route guard for `/user-profile` and `/manage-restaurant`
- `food-ordering-frontend/src/api/*.tsx` / `authApi.ts` — one module per resource (`MyUserApi`, `MyRestaurantApi`, `RestaurantApi`, `OrderApi`, `BusinessInsightsApi`, `CityApi`, `authApi`)

**HTTP client inconsistency** (Confirmed): `MyUserApi.tsx`, `MyRestaurantApi.tsx`, `OrderApi.tsx`, `BusinessInsightsApi.tsx`, and `authApi.ts` use the shared `axiosInstance`. `RestaurantApi.tsx` and `CityApi.tsx` use raw `fetch` directly against `import.meta.env.VITE_API_BASE_URL` for the public restaurant/city endpoints. Two calling conventions coexist today.

**Auth storage** (Confirmed): `localStorage` keys `session_id` (JWT), `user_id`, `user_email`, `user_name`, `user_image`. No cookie is ever set by the app itself (see §5).

### Primary workflows (Confirmed, traced page-by-page)

1. **Browse → search.** `HomePage` / `CityDropdown` populate from `GET /api/restaurant/cities/all` (`src/api/CityApi.tsx`). `SearchPage` (`/search/:city`) filters by cuisine, sorts, and paginates against `GET /api/restaurant/search/:city` (`src/pages/SearchPage.tsx`, `src/api/RestaurantApi.tsx`).
2. **Restaurant detail → cart.** `DetailPage` (`/detail/:restaurantId`, `src/pages/DetailPage.tsx`) keeps the cart in `sessionStorage` under key `cartItems-<restaurantId>`, and explicitly clears it on component unmount via a `useEffect` cleanup — the cart does not survive navigating away from and back to the page.
3. **Checkout.** `CheckoutButton` (`src/components/CheckoutButton.tsx`) opens a dialog with `UserProfileForm` (`src/forms/user-profile-form/UserProfileForm.tsx`) pre-filled from the current user, collects `name`, `addressLine1`, `city`, `country`, `email`; `DetailPage.onCheckout` posts to `create-checkout-session` (`src/api/OrderApi.tsx`) then hard-redirects (`window.location.href`) to the Stripe-hosted page.
4. **Order tracking.** `OrderStatusPage` (`src/pages/OrderStatusPage.tsx`) polls `GET /api/order` every 5s (`refetchInterval: 5000` in `src/api/OrderApi.tsx`). Progress bar stages come from a hard-coded map in `src/config/order-status-config.ts` (5 stages: placed 0%, paid 25%, inProgress 50%, outForDelivery 75%, delivered 100%).
5. **Sign-in.** `SignInPage.tsx` / `RegisterPage.tsx` post directly to the auth endpoints. The "Continue with Google" button (`SignInPage.tsx`) is a full-page redirect to `${VITE_API_BASE_URL}/api/auth/google`; the backend redirects back to `/auth/callback` with the JWT and profile fields **in the URL query string**; `AuthCallbackPage.tsx` reads them and seeds `localStorage`. Every successful login/register/OAuth path ends in a hard `window.location.reload()`.
6. **Restaurant ownership.** `ManageRestaurantPage.tsx` (protected route) has three tabs: "Orders" (statuses `paid`/`inProgress`/`outForDelivery`/`delivered`, with a status-change selector via `EnhancedOrdersTab.tsx`, polled every 5s), "Orders Placed but Not Paid" (status `placed` only, read-only), and "Manage Restaurant" (create/update form, `ManageRestaurantForm.tsx`).
7. **Business insights.** `AnalyticsDashboardPage.tsx` is a **public** route (not wrapped in `ProtectedRoute`) with a 7d/30d/90d/1y time-range selector, calling `src/api/BusinessInsightsApi.tsx`.
8. Secondary pages with no domain-model dependency: `ApiDocsPage.tsx`, `ApiStatusPage.tsx`, `PerformancePage.tsx`.

### Finding: stale env template references Auth0 and client-side Stripe (Confirmed)

`food-ordering-frontend/.env.example` lists `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_CALLBACK_URL`, `VITE_AUTH0_AUDIENCE`, and `VITE_STRIPE_PUB_KEY`. Grep across `food-ordering-frontend/src` confirms none of these are read by any current source file except cosmetic text mentions in `ApiDocsPage.tsx` and `ApiStatusPage.tsx`. The app now uses backend-issued JWTs, server-side Google OAuth, and server-created Stripe Checkout Sessions — these env vars are documentation drift from an earlier architecture.

---

## 2. Backend entry point & application structure

Single entry point, no app factory or DI layer: `food-ordering-backend/src/index.ts`.

```
food-ordering-backend/src/
├── index.ts                       # app bootstrap, CORS, route mounts
├── controllers/
│   ├── AnalyticsController.ts
│   ├── MyRestaurantController.ts
│   ├── MyUserController.ts
│   ├── OrderController.ts
│   └── RestaurantController.ts
├── middleware/
│   ├── auth.ts                    # verifyToken (JWT)
│   └── validation.ts              # express-validator chains
├── models/
│   ├── order.ts
│   ├── restaurant.ts
│   └── user.ts
└── routes/
    ├── AnalyticsRoute.ts
    ├── auth.ts
    ├── MyRestaurantRoute.ts
    ├── MyUserRoute.ts
    ├── OrderRoute.ts
    └── RestaurantRoute.ts
```

### Boot sequence (Confirmed, from `src/index.ts`)

1. `mongoose.connect(process.env.MONGODB_URI || process.env.MONGODB_CONNECTION_STRING)`
2. `cloudinary.config({ cloud_name, api_key, api_secret })`
3. `express()` app created
4. `cors({ origin: [allow-list], credentials: true, methods: [...], allowedHeaders: [...] })`
5. `cookie-parser()`
6. `express.raw({ type: "*/*" })` mounted **only** on `/api/order/checkout/webhook`
7. `express.json()` mounted globally, **after** the raw-body route registration
8. `GET /` → static HTML welcome banner ("BigHungers Food Ordering Backend is Running!")
9. `GET /health` and `GET /api/health` → uptime JSON, computed from an in-process `serverStartTime` closure set at module load (resets on every restart; incorrect under a multi-instance deployment)
10. Route mounts (see §3)
11. `app.listen(process.env.PORT || 5000)`

### Ordering that must be replicated exactly in FastAPI (Confirmed)

The Stripe webhook route needs `express.raw()` registered for its exact path **before** the global `express.json()` middleware, because Stripe's signature check requires the untouched raw request body. In FastAPI this means reading `await request.body()` directly in that one route rather than relying on a global JSON-parsing dependency for all routes.

### CORS allow-list (Confirmed, `src/index.ts`)

`process.env.FRONTEND_URL`, `http://localhost:5173`, `http://localhost:3000`, `https://mern-food-ordering.netlify.app`, `https://mern-food-ordering-hnql.onrender.com`. `credentials: true`; methods `GET, POST, PUT, DELETE, PATCH, OPTIONS`; headers `Content-Type, Authorization, Cookie, X-Requested-With`.

### Finding: two deployment lineages appear in the same codebase (Needs confirmation)

The CORS list and the `// Root route for Render deployment` comment in `src/index.ts` point at Render + Netlify. `food-ordering-backend/Dockerfile` comments ("In Coolify: Base Directory = food-ordering-backend...", "In Coolify set PORT=3000 and Ports Mappings 5002:3000") point at Coolify, a different self-hosted target. **Which platform actually serves production today needs confirmation** before assuming either deployment path in the rewrite.

---

## 3. API inventory (routes & controllers)

22 endpoints across 6 route files, each delegating to a plain object-of-functions controller (no service layer — controllers call Mongoose models directly).

### `/api/auth` → `food-ordering-backend/src/routes/auth.ts` (logic lives in the route file; no separate controller)

| Method | Path | Auth | Notes (Confirmed) |
|---|---|---|---|
| GET | `/google` | — | Hand-built Google OAuth redirect URL (no Passport.js). Generates a `state` nonce via `crypto.randomBytes(32)` that is **never stored or checked** on callback. |
| GET | `/callback/google` | — | Exchanges `code` for a token via `fetch` to Google's token endpoint, fetches userinfo, upserts `User` by email (new users get a random, never-shown password), signs a 1-day JWT, **redirects to the frontend with token + profile fields as URL query params**. |
| POST | `/register` | — | express-validator inline checks (`email`, `password` ≥ 6 chars, `name` required); 201 + JWT. |
| POST | `/login` | — | bcrypt compare against stored hash; 200 + JWT. |
| GET | `/validate-token` | JWT | Returns `{ userId }`. |
| POST | `/logout` | — | Clears a `session_id` cookie that the app never sets (see §5). |

### `/api/my/user` → `food-ordering-backend/src/controllers/MyUserController.ts`

| Method | Path | Auth | Notes (Confirmed) |
|---|---|---|---|
| GET | `/` | JWT | Current user by `req.userId`; 404 if not found. |
| POST | `/` | JWT | `createCurrentUser` **does not create anything** — it checks for an existing user and returns 200, else 404 "User not found." Real account creation only happens via `/api/auth/register` or the Google callback. Reads as dead/legacy code. |
| PUT | `/` | JWT | Validated by `validateMyUserRequest`; overwrites `name`, `addressLine1`, `city`, `country`. |

### `/api/my/restaurant` → `food-ordering-backend/src/controllers/MyRestaurantController.ts`

| Method | Path | Auth | Notes (Confirmed) |
|---|---|---|---|
| GET | `/order` | JWT | All orders for the caller's restaurant, **including unpaid `placed` orders**. |
| PATCH | `/order/:orderId/status` | JWT | Ownership check via `restaurant.user._id.toString() === req.userId`. `orderId` validated as a Mongo ObjectId. No app-level check that `status` is one of the five valid enum values — an invalid value throws at `.save()` (Mongoose enum validation), caught generically and returned as a 500. |
| GET | `/` | JWT | Returns `null` with 200 when the caller has no restaurant (used by the frontend to decide create-vs-edit mode). |
| POST | `/` | JWT † | Middleware order: `upload.single("imageFile")` → `validateMyRestaurantRequest` → `verifyToken` → controller. See callout below. |
| PUT | `/` | JWT † | Same middleware order as POST. |

**† Middleware order finding (Confirmed):** in `food-ordering-backend/src/routes/MyRestaurantRoute.ts`, multer (memory storage, 5MB limit) and full field validation both run **before** `verifyToken`. An unauthenticated request still pays the cost of parsing an up-to-5MB multipart body and running validation before being rejected for lack of auth.

### `/api/restaurant` → `food-ordering-backend/src/controllers/RestaurantController.ts` (public)

| Method | Path | Notes (Confirmed) |
|---|---|---|
| GET | `/cities/all` | `Restaurant.distinct("city")`. |
| GET | `/:restaurantId` | ObjectId shape validated inside the controller; the route-level `param()` check (in `RestaurantRoute.ts`) only confirms a non-empty string. |
| GET | `/search/:city` | Query params: `searchQuery`, `selectedCuisines` (comma-separated, matched with Mongo `$all` — a restaurant must have **every** selected cuisine, not any), `sortOption` (default `lastUpdated`, **always sorted ascending** regardless of field), `page` (default 1, page size fixed at 10). `city="all"` or empty skips the city filter. Regex objects are built from raw user input with no escaping of regex metacharacters. |

### `/api/order` → `food-ordering-backend/src/controllers/OrderController.ts`

| Method | Path | Auth | Notes (Confirmed) |
|---|---|---|---|
| GET | `/` | JWT | Filters `status IN [placed, paid, inProgress, outForDelivery, delivered]` — this is the complete enum, so the filter currently excludes nothing. |
| POST | `/checkout/create-checkout-session` | JWT | See §6. |
| POST | `/checkout/webhook` | Stripe signature (no JWT) | Intentionally public; protected by Stripe signature verification instead of a JWT. |

### `/api/business-insights` → `food-ordering-backend/src/controllers/AnalyticsController.ts`

| Method | Path | Auth | Notes (Confirmed) |
|---|---|---|---|
| GET | `/` | JWT | Global (not per-restaurant) analytics aggregate. |
| GET | `/public` | — | **Calls the identical handler function** as the route above — same output. |
| GET | `/test` | — | Calls the identical handler again; source comment reads `// Development endpoint for testing (remove in production)` and it is still mounted. |
| GET | `/db-test` | — | Returns a raw `Order.countDocuments()`. |
| GET | `/debug-orders` | — | Dumps every order's id, city, amount, `createdAt`, restaurant name/cuisines — no auth. |
| GET | `/debug-restaurants` | — | Dumps every restaurant's id, name, cuisines, city — no auth. |

**Finding (Confirmed):** five of six analytics endpoints are unauthenticated, and even the one behind `verifyToken` returns the same global aggregate as the public route — logging in changes nothing about the data returned, only whether a valid token is required to call that one specific path.

---

## 4. Database models & relationships

Three top-level Mongoose collections. No role/permission field anywhere; ownership is entirely inferred from foreign-key matches at query time. No schema-level uniqueness beyond `User.email`.

### `User` — `food-ordering-backend/src/models/user.ts`

| Field | Type | Notes (Confirmed) |
|---|---|---|
| `email` | String | required, unique index |
| `password` | String | required; bcrypt-hashed (cost factor 8) in a `pre("save")` hook, only when the field was modified |
| `name`, `addressLine1`, `city`, `country`, `image` | String | all optional |

No `role` / `isRestaurantOwner` field exists. Any authenticated user can attempt to create a restaurant; the only guard is an application-level check in the controller, not a database constraint.

### `Restaurant` — `food-ordering-backend/src/models/restaurant.ts`

| Field | Type | Notes (Confirmed) |
|---|---|---|
| `user` | ObjectId → User | owner reference; not `required` at schema level |
| `restaurantName`, `city`, `country` | String | required |
| `deliveryPrice` | Number | required — **stored as an integer in pence**, converted server-side from the pounds-and-pence float the form submits |
| `estimatedDeliveryTime` | Number | required (minutes, implied by the UI, not asserted by the schema) |
| `cuisines` | [String] | required, non-empty (enforced at the route validation layer) |
| `menuItems` | [{ `_id`, `name`, `price` }] | embedded subdocuments; `_id` auto-generated per item; `price` is integer pence, same conversion rule as `deliveryPrice` |
| `imageUrl` | String | required — Cloudinary `.url` (plain HTTP, not `.secure_url`) |
| `lastUpdated` | Date | required, set by the controller on every create/update |

### `Order` — `food-ordering-backend/src/models/order.ts`

| Field | Type | Notes (Confirmed) |
|---|---|---|
| `restaurant`, `user` | ObjectId refs | not `required` at schema level |
| `deliveryDetails` | `{ email, name, addressLine1, city }` | all required — **no `country` field** |
| `cartItems` | `[{ menuItemId: String, quantity: Number, name: String }]` | a snapshot copy, not a live reference — **no per-line `price` is persisted** |
| `totalAmount` | Number | integer pence; written twice over the order lifecycle (see §6) |
| `status` | enum String | `placed \| paid \| inProgress \| outForDelivery \| delivered`; no schema-level default (the controller always sets `"placed"` explicitly on create) |
| `createdAt` | Date | schema default `Date.now`, and also set again explicitly by the controller (redundant, harmless) |

### Finding: delivery `country` is collected but never persisted (Confirmed)

`UserProfileForm.tsx` collects `country` (zod-required field), and `DetailPage.tsx`'s `onCheckout` sends it inside `deliveryDetails` to `POST /api/order/checkout/create-checkout-session`. The `Order` schema's `deliveryDetails` sub-schema (`models/order.ts`) has no `country` field, and Mongoose subdocuments are strict by default, so the value is silently dropped when the order document is constructed in `OrderController.ts`.

### Finding: historical per-item price is not recoverable from an order (Confirmed)

`createCheckoutSession` (`OrderController.ts`) looks up each cart item's price from the restaurant's **current** `menuItems` only to compute the aggregate `totalAmount`; the resolved price is never written onto the saved `cartItems` subdocuments. If a menu price changes later, past orders retain the total but not the line-item price that produced it.

### Relationships (Confirmed)

- `User` 1—0/1 `Restaurant` (owner, application-enforced, not a DB constraint)
- `User` 1—N `Order` (customer)
- `Restaurant` 1—N `Order`
- `Restaurant` 1—N embedded `MenuItem` (not a separate collection)

---

## 5. Authentication & authorization flow

Single JWT scheme covering three entry paths (password, register, Google OAuth). No roles, no refresh tokens, no revocation.

### `middleware/auth.ts` — `verifyToken` (Confirmed)

```
token = Authorization: "Bearer <token>"   (checked first)
        OR req.cookies["session_id"]      (fallback)
jwt.verify(token, process.env.JWT_SECRET_KEY) → req.userId = payload.userId
any failure → 401 { message: "unauthorized" }
```

### Finding: the cookie fallback path is currently dead (Confirmed)

Nothing in the app ever calls `res.cookie(...)` to set `session_id`. `/login` and `/register` (`routes/auth.ts`) return the JWT only in the JSON response body; the Google callback returns it as a URL query parameter. The frontend always stores the token in `localStorage` and sends it as a Bearer header. `POST /api/auth/logout` still clears a `session_id` cookie that was never set.

### Finding: Google OAuth's CSRF `state` parameter is decorative (Confirmed)

`crypto.randomBytes(32)` is generated and appended to the authorization URL in `GET /google`, but it is never stored (session, cookie, or cache) and never compared in `GET /callback/google`. It currently provides no CSRF protection.

### Finding: Google-created accounts cannot use the password login (Confirmed / needs product confirmation)

New users created via the OAuth callback get a `crypto.randomBytes(32)` password they never see, and there is no password-reset flow anywhere in the codebase. This is very likely intentional (Google is the only path in for those accounts), but **needs confirmation** as a product decision rather than an oversight.

### Authorization model (Confirmed)

No role field anywhere. "Restaurant owner" status is purely "a `Restaurant` document exists with `user === req.userId`," re-checked per request inside each controller — there is no centralized authorization layer.

---

## 6. Stripe payment & webhook integration

Server-side Stripe Checkout Sessions, GBP-only currently. The webhook is the single source of truth for marking an order "paid."

### Checkout session creation — `OrderController.createCheckoutSession` (Confirmed)

1. Load the `Restaurant`; build an **unsaved** `Order` document with `status: "placed"`.
2. Compute a subtotal by matching each cart item's `menuItemId` against `restaurant.menuItems._id` (string comparison) — **a miss here silently defaults the item's price to 0**.
3. Build Stripe line items via a **second, separate** lookup over the same `menuItems` array — a miss there **throws** `Menu item not found: <id>`. The two lookups disagree on failure behavior for the same underlying condition.
4. `totalAmount = subtotal + restaurant.deliveryPrice` (pence), assigned to the in-memory order.
5. Create the Stripe Checkout Session: currency hard-coded `"gbp"` in two separate places (line items and the shipping-rate delivery cost); `metadata: { orderId, restaurantId }`; `success_url` → `${FRONTEND_URL}/order-status?success=true`; `cancel_url` → `${FRONTEND_URL}/detail/:restaurantId?cancelled=true`.
6. The `Order` is only `.save()`'d **after** Stripe returns a session with a non-empty `url` — if session creation fails, no order document is ever written to the database.

### Finding: non-Stripe errors crash the checkout error handler (Confirmed)

```ts
catch (error: any) {
  res.status(500).json({ message: error.raw.message });
}
```
This assumes every thrown error is a Stripe SDK error carrying a `.raw` property. The plain `throw new Error("Restaurant not found")` a few lines above in the same function has no `.raw`, so that specific failure path throws a second, unhandled `TypeError` inside the `catch` block instead of returning the intended JSON error message.

### Webhook — `OrderController.stripeWebhookHandler` (Confirmed)

`POST /api/order/checkout/webhook` verifies the request via `STRIPE.webhooks.constructEvent(rawBody, signatureHeader, STRIPE_WEBHOOK_SECRET)`, which requires the raw-body middleware described in §2. Only the `checkout.session.completed` event type is handled — every other Stripe event type falls through to an unconditional `200` response with no side effect (no handling of expired sessions, failed payments, or refunds). On a match: validates `metadata.orderId` is a valid ObjectId, loads the order, sets `totalAmount = event.data.object.amount_total` and `status = "paid"`, then saves.

### Finding: two totals, one field (Confirmed)

The app computes a provisional `totalAmount` at session-creation time (step 4 above) and the webhook later overwrites it with Stripe's authoritative `amount_total`. They are expected to match, but nothing in the code enforces or reconciles them if they don't.

---

## 7. Cloudinary / file-upload integration

Used in exactly one place: the restaurant image on create/update (`MyRestaurantController.ts`, `uploadImage` helper). No other upload surface exists in the codebase.

- **Transport** (Confirmed): multer with `memoryStorage()` (files never touch disk) and a 5MB size limit (`limits.fileSize`), configured in `routes/MyRestaurantRoute.ts`; field name `imageFile`. No `fileFilter` is configured — any mimetype is accepted at the multer layer.
- **Upload call** (Confirmed): buffer → base64 → `data:<mimetype>;base64,...` data URI → `cloudinary.v2.uploader.upload(dataURI)` (the data-URI form of the API, not the streaming upload). The returned `.url` (plain HTTP) is stored on `Restaurant.imageUrl` — not `.secure_url`.
- **No cleanup** (Confirmed): updating a restaurant's image never deletes the previous Cloudinary asset, and no `public_id` is stored on the `Restaurant` model, so orphaned assets cannot be cleaned up retroactively from current data alone.

---

## 8. Restaurant, menu, order, user & analytics — cross-cutting business rules

Rules below don't belong to any single route and are easy to drop by accident during a rewrite.

- **Money is always integer pence in the database** (Confirmed). `Restaurant.deliveryPrice`, `menuItems[].price`, and `Order.totalAmount` are all integers in the smallest currency unit. The form layer sends/receives decimal pounds (e.g. `6.90`); the conversion `Math.round(parseFloat(x) * 100)` happens only in `MyRestaurantController.ts`, on both create and update. Stripe is given the same pence values directly (its API also expects the smallest unit), so no second conversion happens there.
- **Analytics is global, not per-restaurant** (Confirmed / needs product confirmation). `getAnalyticsData` (`AnalyticsController.ts`) aggregates every order in the database regardless of who is asking — there is no filter by the caller's own restaurant anywhere in the function. "Logged in" only changes which URL the frontend calls (`/api/business-insights` vs `/api/business-insights/public`); the output is identical. Whether this is intended as a platform-wide dashboard or should be scoped per-owner needs confirmation, since the UI's "Business Insights" language reads as owner-specific.
- **Search cuisine filter is an AND, not an OR** (Confirmed). `selectedCuisines` is matched with Mongo's `$all` in `RestaurantController.searchRestaurant` — a restaurant must offer every selected cuisine simultaneously to appear.
- **"My orders" for a customer is effectively unfiltered** (Confirmed). `getMyOrders` (`OrderController.ts`) filters `status IN [placed, paid, inProgress, outForDelivery, delivered]` — the complete enum — so the filter currently excludes nothing.
- **One restaurant per user, enforced only in application code** (Confirmed). No unique index on `Restaurant.user`; the guard is a `findOne` check before `.save()` inside `createMyRestaurant`, which leaves a race window under concurrent requests.

---

## 9. Validation, error handling & middleware

### Finding: validation-error response shape is inconsistent (Confirmed)

`middleware/validation.ts`'s `handleValidationErrors` returns `400 { errors: [...] }` (used by `validateMyUserRequest` and `validateMyRestaurantRequest`). The inline `check()` validation in `routes/auth.ts` returns `400 { message: [...] }` instead — the same failure class produces two different JSON shapes depending on which endpoint is hit.

### Other confirmed observations

- **No global/centralized error handler.** Every controller has its own `try/catch` with an ad hoc `{ message: "..." }` body and its own status code choice; anything thrown outside those blocks falls through to Express's default handler and returns an HTML error page instead of JSON.
- **No request logging middleware** (no morgan/pino) — only scattered `console.log`/`console.error` calls, heaviest in `AnalyticsController.ts`.
- **No rate limiting, no helmet-style security headers, no input sanitization** beyond express-validator's presence/type checks. Free-text fields (restaurant name, city, delivery name) are stored and returned as-is; XSS mitigation currently depends entirely on React's default output escaping on the frontend.
- **Unescaped regex from user input.** `searchRestaurant` (`RestaurantController.ts`) builds `new RegExp(input, "i")` directly from `city`, `selectedCuisines`, and `searchQuery` query parameters, with no escaping of regex metacharacters.
- **Multer errors are uncaught at the app level.** A file over the 5MB limit raises a `MulterError` that is not translated into the app's usual JSON error shape.

---

## 10. Tests, build scripts & deployment configuration

### No automated test suite (Confirmed)

A repository-wide search for `*.test.*` and `*spec*` returns nothing relevant — the only match is an unrelated shadcn UI component literally named `aspect-ratio.tsx` (a false positive on the substring "spec"). There is no Jest/Vitest/Mocha configuration anywhere, and no `.github/workflows` directory — no CI pipeline exists in the repository.

### Backend build & run (Confirmed, `food-ordering-backend/package.json` and `Dockerfile`)

| Script/Artifact | Value |
|---|---|
| `dev` | `concurrently "nodemon" "npm run stripe"` — runs the Stripe CLI's local webhook forwarder alongside the dev server |
| `dev:no-stripe` | `nodemon` |
| `stripe` | `stripe listen --forward-to localhost:5000/api/order/checkout/webhook` |
| `build` | `npm install && npx tsc` → emits to `dist/` |
| `start` | `node dist/index.js` |
| Docker | Multi-stage (`node:20-alpine` builder + runner), `npm ci --only=production` in the final stage, healthcheck hits `/api/health`, `EXPOSE 3000` while the app defaults to port 5000 unless `PORT` is set |
| Seed script | `scripts/create-test-user.ts` creates `test@user.com` / `12345678` directly via Mongoose — this is the exact account wired into the "Guest User" dropdown on `SignInPage.tsx`, so it is an active part of the demo workflow, not leftover cruft |

### Frontend build & deploy (Confirmed, `food-ordering-frontend/package.json` and root config files)

| Script/Artifact | Value |
|---|---|
| `build` | `tsc && vite build` |
| `lint` | `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0` (strict — zero warnings tolerated) |
| Hosting configs present | `netlify.toml` (SPA redirect + image cache headers) **and** `vercel.json` (SPA rewrite) are both committed in the repo — see the deployment-lineage discrepancy noted in §2 |

---

## Environment variables in current use (Confirmed)

| Variable | Consumed by | Purpose |
|---|---|---|
| `MONGODB_URI` (falls back to `MONGODB_CONNECTION_STRING`) | backend, `scripts/create-test-user.ts` | primary database connection string |
| `JWT_SECRET_KEY` | backend | signs/verifies all JWTs |
| `FRONTEND_URL` | backend | CORS allow-list entry; OAuth and Stripe redirect target |
| `BACKEND_URL` | backend | builds the Google OAuth redirect URI |
| `GOOGLE_ID` / `GOOGLE_SECRET` | backend | Google OAuth client credentials |
| `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | backend | image upload |
| `STRIPE_API_KEY` | backend | Stripe SDK auth |
| `STRIPE_WEBHOOK_SECRET` | backend | webhook signature verification |
| `PORT` | backend | listen port, default 5000 |
| `VITE_API_BASE_URL` | frontend | backend base URL, used by both the shared Axios instance and the raw-`fetch` API modules |

Not consumed by any current source file, but present in `food-ordering-frontend/.env.example` (documentation drift, see §1): `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_CALLBACK_URL`, `VITE_AUTH0_AUDIENCE`, `VITE_STRIPE_PUB_KEY`.

---

## Unverified areas requiring confirmation before modernization design

1. **Production deployment target.** CORS allow-list and code comments in `src/index.ts` point at Render + Netlify; `Dockerfile` comments point at Coolify. Needs confirmation which is authoritative today.
2. **Intended scope of "Business Insights."** Currently global across all orders/restaurants regardless of caller. Needs a product decision on whether the FastAPI port should scope it per-restaurant.
3. **Fate of the debug/test analytics endpoints** (`/test`, `/db-test`, `/debug-orders`, `/debug-restaurants`) — whether to port them at all, and if so, behind what authorization.
4. **Purpose of the never-set `session_id` cookie** and the matching `verifyToken` cookie-fallback logic — confirm whether this is a legacy remnant safe to drop, or a signal that cookie-based sessions were once (or should be) the real mechanism.
5. **Whether losing the delivery `country` field is an accepted gap** or should be corrected in the new schema.
6. **Whether clearing the cart on every unmount of `DetailPage`** is intended UX or an unnoticed side effect of the current `sessionStorage` implementation.
7. **Runtime behavior of all of the above** — none of it was exercised against a live server or live MongoDB/Stripe/Cloudinary/Google credentials during this analysis; all findings are static-code observations only.

## Modernization constraints (Confirmed, must be preserved unless explicitly changed by product decision)

- **Raw-body Stripe webhook ordering**: the FastAPI route handling `/api/order/checkout/webhook` must read the unparsed request body for signature verification, mirroring the `express.raw()`-before-`express.json()` ordering in `src/index.ts`.
- **Pence-integer money representation** across `Restaurant.deliveryPrice`, `menuItems[].price`, and `Order.totalAmount`, with pounds-to-pence conversion happening at the API boundary, not in the database layer.
- **JWT payload shape** `{ userId }`, 1-day expiry, validated via `Authorization: Bearer <token>` — this is what the existing frontend already sends on every authenticated request and cannot be changed without a frontend change.
- **CORS origins and credentials mode** must continue to admit the existing frontend origins with `credentials: true` for cookie/Authorization-header support to keep working across the current allow-list.
- **Existing response shapes** consumed directly by frontend code (e.g., `{ url }` from checkout session creation, `{ cities: [...] }` from the cities endpoint, `{ data, pagination: { total, page, pages } }` from restaurant search) must be matched exactly unless the frontend is updated in lockstep.
- **No test suite exists to validate behavioral parity** — any modernization effort starts without a regression safety net and should budget for building one alongside the port, not assume one can be "migrated."
