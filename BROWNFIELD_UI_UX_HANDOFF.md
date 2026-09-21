# Brownfield UI/UX Handoff Specification
## Restaurant Food Ordering Management System — Backend Modernization (Node.js/Express → Python/FastAPI)

**Basis:** Direct re-inspection of `food-ordering-frontend/src` (all pages, layout, navigation, and shared components) and `food-ordering-backend/src` (all routes/controllers), cross-checked against `CURRENT_STATE.md`, `BUSINESS_PROBLEM_STATEMENT.md`, `BRD.md`, and `PRD.md`. No application source code was modified to produce this document. No screenshots were generated — all descriptions are derived from reading the actual `.tsx` source.

**Labels used throughout:** **CONFIRMED** (read directly in source), **OBSERVED** (seen while running the app — none in this document, the app was not executed), **NEEDS CONFIRMATION** (ambiguous from static code alone).

---

## 1. Purpose and Scope

This document describes the **existing** user interface of the BigHungers food-ordering application exactly as implemented today, and specifies the UI-side and API-contract changes required to support replacing the Node.js/Express backend with a Python/FastAPI backend. It is the handoff artifact the modernization team will convert into Jira tasks.

This is **not** a redesign brief. The frontend (React/TypeScript/Vite), its component library (shadcn/ui + Tailwind), its navigation, and its visual language all remain as they are. The only UI-relevant work in scope is what is strictly necessary so the same frontend continues to function, unchanged in appearance and behavior, against a FastAPI backend instead of an Express backend. Tool constraint: this handoff is produced for use with Claude and Jira only — no Stitch, Figma, or other external UI-generation tool was used or is assumed downstream.

## 2. Brownfield Principles

- **Preserve existing user workflows.** Every journey documented in §4 must work identically after the backend swap.
- **Preserve existing navigation and information architecture.** The route table, the header/mobile navigation links, and the page hierarchy in `AppRoutes.tsx` are not to be restructured.
- **Preserve the current visual language unless a change is required.** Colors, typography, spacing, and shadcn/ui component usage stay as-is.
- **Avoid unnecessary redesign.** No screen in this document should be rebuilt from scratch; changes are additive/corrective only.
- **Do not change business behavior without approval.** Order-status meanings, pricing rules, and search/filter semantics are carried over exactly (see `CURRENT_STATE.md` §8) unless a named open question is resolved by the business owner.
- **Keep frontend changes minimal where possible.** Most required changes are backend-side; frontend changes are limited to what a different backend implementation might expose differently (e.g., a corrected validation-error shape), and only if that correction is explicitly approved.
- **Clearly distinguish confirmed facts from assumptions.** Every claim below is labeled CONFIRMED, OBSERVED, or NEEDS CONFIRMATION; nothing is asserted as fact without a source.

---

## 3. Existing Application UI Inventory

All routes below are read directly from `food-ordering-frontend/src/AppRoutes.tsx`. "User role" reflects the access model actually implemented: there is **no server-side or client-side role field** (CONFIRMED, `CURRENT_STATE.md` §4) — "Restaurant Owner" below means "any authenticated user who has chosen to create a restaurant," not a distinct account type.

| Screen | Route | User role | Main purpose | Important components | Related API endpoints | Status |
|---|---|---|---|---|---|---|
| Home | `/` | Guest / Any | Landing page; city/keyword search entry point | `Hero`, `SearchBar`, `CityDropdown` | `GET /api/restaurant/cities/all` | CONFIRMED |
| Sign In | `/sign-in` | Guest | Password login, Google OAuth entry, seeded test-account picker | `SignInPage` form, `Select` (test accounts) | `POST /api/auth/login`, `GET /api/auth/google` (full redirect) | CONFIRMED |
| Register | `/register` | Guest | Email/password/name account creation | `RegisterPage` form | `POST /api/auth/register` | CONFIRMED |
| Auth Callback | `/auth/callback` | Guest (mid-flow) | Consumes Google OAuth redirect query params, seeds `localStorage`, redirects | `AuthCallbackPage` | None directly — depends on `GET /api/auth/callback/google` having already run server-side | CONFIRMED |
| Search Results | `/search/:city` | Guest / Any | Filter, sort, paginate restaurants by city/cuisine/keyword | `CuisineFilter`, `SearchBar`, `SortOptionDropdown`, `SearchResultCard`, `PaginationSelector` | `GET /api/restaurant/search/:city`, `GET /api/restaurant/cities/all` | CONFIRMED |
| Restaurant Detail | `/detail/:restaurantId` | Guest / Any | View menu, build cart, initiate checkout | `MenuItem`, `OrderSummary`, `CheckoutButton`, `UserProfileForm` (dialog) | `GET /api/restaurant/:restaurantId`, `GET /api/my/user`, `POST /api/order/checkout/create-checkout-session` | CONFIRMED |
| Order Status | `/order-status` | Authenticated | Track own orders, grouped by date, with a payment-success toast | `OrderStatusHeader`, `OrderStatusDetail`, `OrderRightColumn` | `GET /api/order` | CONFIRMED |
| API Docs | `/api-docs` | Guest / Any | Static, hand-written API reference page | Tabs, `Card` list | None live (reference text only) | CONFIRMED — **contains at least one endpoint that does not exist in the backend** (see §12) |
| API Status | `/api-status` | Guest / Any | Health dashboard | `Card`, `Progress`, `Badge` | `GET /health`, `GET /api/business-insights/db-test` (real); Stripe/Cloudinary/"Auth0" rows are simulated (see §12) | CONFIRMED |
| Business Insights | `/business-insights` | Guest / Any | Revenue/orders/cuisine/city analytics dashboard | `Card` stat tiles, tables | `GET /api/business-insights` (logged in) or `GET /api/business-insights/public` (logged out) | CONFIRMED |
| Optimization | `/optimization` | Guest / Any | Client-side performance self-analysis (Navigation/Resource Timing APIs) | `PerformanceOptimizer` | **None** — entirely browser-API-driven, no backend calls | CONFIRMED |
| User Profile | `/user-profile` | Authenticated (protected) | View/edit name, address, city, country | `UserProfileForm` | `GET /api/my/user`, `PUT /api/my/user` | CONFIRMED |
| Manage Restaurant | `/manage-restaurant` | Authenticated (protected) | Create/edit restaurant + menu; view and update incoming orders | `Tabs`, `EnhancedOrdersTab`, `ManageRestaurantForm` | `GET /api/my/restaurant`, `POST /api/my/restaurant`, `PUT /api/my/restaurant`, `GET /api/my/restaurant/order`, `PATCH /api/my/restaurant/order/:orderId/status` | CONFIRMED |
| (wildcard) | `*` | Any | Redirects to `/` | — | — | CONFIRMED |

## 4. Existing User Journeys

Every journey below is CONFIRMED from source unless marked otherwise. "Authorization requirements" reflects `ProtectedRoute` (route-level, only for `/user-profile` and `/manage-restaurant`) plus per-request JWT checks by individual API hooks (`enabled: !!localStorage.getItem("session_id")`).

### Customer signs in
- **Start:** `/sign-in`.
- **Steps:** Enter email/password (or pick the seeded "Guest User" test account) → submit → `authApi.signIn` posts to `/api/auth/login` → token/user fields written to `localStorage` → `react-query` cache invalidated → redirect to the page the user came from (or `/`) → **hard `window.location.reload()`**.
- **Screens involved:** `SignInPage`.
- **API calls:** `POST /api/auth/login`.
- **Success state:** toast "Signed in successfully!", then reload.
- **Loading state:** submit button shows "Signing in..." (`isLoading` disables the button; no skeleton).
- **Empty state:** N/A (form-based).
- **Error state:** toast with the caught error's `.message`, or "Invalid credentials" fallback.
- **Authorization:** none required to view the page.

### Customer signs in with Google
- **Start:** `/sign-in`, "Continue with Google" button.
- **Steps:** Full-page redirect to `${VITE_API_BASE_URL}/api/auth/google` → Google consent → backend `GET /api/auth/callback/google` → redirect to `/auth/callback?token=...&userId=...&email=...&name=...&image=...` → `AuthCallbackPage` seeds `localStorage` → invalidates `validateToken` query → navigates to `/` → hard reload.
- **Screens involved:** `SignInPage`, `AuthCallbackPage`.
- **API calls:** `GET /api/auth/google`, `GET /api/auth/callback/google` (both are full navigations, not `fetch`/`axios` calls).
- **Success state:** lands on `/` authenticated.
- **Loading state:** `AuthCallbackPage` shows a centered spinner with "Completing sign-in...".
- **Error state:** if `?error=...` is present, redirected to `/sign-in?error=...` (no toast is shown for this specific case — **NEEDS CONFIRMATION** whether the query param is surfaced anywhere in the UI; source shows no code reading it on `SignInPage`).
- **Authorization:** none.

### Customer searches for a restaurant
- **Start:** `/` (Home) or directly `/search/:city`.
- **Steps:** Type a city (autosuggest after 2+ characters) and/or a keyword → submit → navigate to `/search/:city?searchQuery=...` → `SearchPage` loads, calls the search endpoint with cuisine/sort/page state.
- **Screens involved:** `HomePage`, `SearchPage`.
- **API calls:** `GET /api/restaurant/cities/all` (city list/validation), `GET /api/restaurant/search/:city`.
- **Success state:** result cards + pagination.
- **Loading state:** on Home, a skeleton search bar while cities load; on Search, 5 skeleton result cards.
- **Empty state:** "Sorry, there is no restaurant near to your search area." (shown both when the city isn't in the known list and when the API returns zero results).
- **Error state:** **NEEDS CONFIRMATION** — `useSearchRestaurants`/`useCitySearch` use raw `fetch` with no error-state UI beyond `isLoading`; a rejected promise is not caught or surfaced to the user in the current code.
- **Authorization:** none.

### Customer views restaurant details
- **Start:** clicking a `SearchResultCard`.
- **Steps:** Navigate to `/detail/:restaurantId` → fetch restaurant → render menu.
- **Screens involved:** `DetailPage`.
- **API calls:** `GET /api/restaurant/:restaurantId`.
- **Success state:** hero image, restaurant info, menu list, order summary panel.
- **Loading state:** full skeleton layout (image + menu-item placeholders + summary card).
- **Empty state:** N/A (a restaurant with zero menu items would render an empty menu list — **NEEDS CONFIRMATION**, no explicit empty-menu message exists in source).
- **Error state:** **NEEDS CONFIRMATION** — no explicit "restaurant not found" UI is rendered; `isLoading` stays true if the query never resolves data, and a 404/400 from the API is not visibly handled.
- **Authorization:** none to view; see checkout below for the authenticated step.

### Customer selects food items
- **Start:** `DetailPage`, clicking a `MenuItem` card.
- **Steps:** Click adds one unit to a cart held in `sessionStorage` (`cartItems-<restaurantId>`); `OrderSummary` shows a per-item quantity stepper and remove button; the cart is cleared automatically when the component unmounts (navigating away).
- **Screens involved:** `DetailPage`, `MenuItem`, `OrderSummary`.
- **API calls:** none — entirely client-side state.
- **Success state:** running subtotal/delivery/total updates live.
- **Empty state:** "Your cart is empty. Add items from the menu to get started."
- **Error state:** N/A.
- **Authorization:** none.

### Customer checks out
- **Start:** `OrderSummary`'s "Go to checkout" button (via `CheckoutButton`).
- **Steps:** If not logged in, button becomes a "Log in to check out" link. If logged in, opens a dialog with `UserProfileForm` pre-filled from the current user → submit → `onCheckout` builds the checkout payload → `POST /api/order/checkout/create-checkout-session` → full-page redirect (`window.location.href`) to the Stripe-hosted page → Stripe redirects back to `/order-status?success=true` (success) or `/detail/:id?cancelled=true` (cancel).
- **Screens involved:** `DetailPage`, `CheckoutButton`, `UserProfileForm` (dialog), Stripe-hosted page (external), `OrderStatusPage`.
- **API calls:** `GET /api/my/user` (dialog prefill), `POST /api/order/checkout/create-checkout-session`.
- **Success state:** green toast "Payment Successful!" on `OrderStatusPage` after the Stripe redirect.
- **Loading state:** `CheckoutButton` renders a `LoadingButton` while `useGetMyUser` is loading; the dialog's submit button shows the same during session creation.
- **Empty state:** N/A (button is `disabled` when the cart is empty).
- **Error state:** a toast with the caught error's message on checkout-session failure (note: `CURRENT_STATE.md` §6 documents a backend bug where a non-Stripe error can crash the handler and return an unexpected shape — the frontend's generic toast would still display *something*, but not necessarily a meaningful message in that case).
- **Authorization:** requires a valid session for the checkout-session call; browsing/cart-building does not.

### Customer views order history
- **Start:** `/order-status` (or the "Order Status" nav link).
- **Steps:** Loads all of the user's orders, groups them by date (newest first, collapsible per date), shows a status badge and progress per order.
- **Screens involved:** `OrderStatusPage`, `OrderStatusHeader`, `OrderStatusDetail`, `OrderRightColumn`.
- **API calls:** `GET /api/order` (polled every 5s, CONFIRMED via `refetchInterval: 5000`).
- **Success state:** grouped order cards with restaurant, delivery, and item detail.
- **Loading state:** 2 skeleton order cards.
- **Empty state:** "No Orders Found — You haven't placed any orders yet..."
- **Error state:** not logged in → a dedicated "sign in to view orders" card with test credentials shown (this is a real, currently-visible UI state, CONFIRMED). No distinct "API failed" state is coded beyond the loading/empty branches.
- **Authorization:** the page itself renders for anyone, but shows the "please sign in" card unless `isLoggedIn`.

### Customer tracks an order
- Same screen and data source as "views order history" above — tracking is the same `/order-status` list with live status badges, a progress bar (`OrderStatusHeader`, values from `order-status-config.ts`: placed 0%, paid 25%, inProgress 50%, outForDelivery 75%, delivered 100%), and a red "Payment Required" banner for orders still in `placed` status.

### Restaurant owner signs in
- Identical flow to "Customer signs in" above — there is no separate owner login. Ownership is determined only by whether a `Restaurant` document exists for the signed-in user (CONFIRMED, `CURRENT_STATE.md` §4/§5).

### Restaurant owner creates or updates a restaurant
- **Start:** `/manage-restaurant` → "Manage Restaurant" tab.
- **Steps:** `ManageRestaurantForm` (zod-validated) collects name/city/country/delivery price/estimated delivery time/cuisines (checkbox list of 26 hardcoded options)/menu items/image → submit as `multipart/form-data` → `POST` (create) or `PUT` (update).
- **Screens involved:** `ManageRestaurantPage`, `ManageRestaurantForm` and its sub-sections (`DetailsSection`, `CuisinesSection`, `MenuSection`, `ImageSection`).
- **API calls:** `GET /api/my/restaurant` (to decide create vs. edit mode), `POST /api/my/restaurant` or `PUT /api/my/restaurant`.
- **Success state:** toast "Restaurant created successfully!" / "Restaurant updated successfully!".
- **Loading state:** submit button becomes a `LoadingButton`.
- **Empty state:** a brand-new owner sees the form pre-filled with one blank menu-item row.
- **Error state:** toast "Unable to create/update restaurant" on failure (no field-level server-error mapping beyond zod's own client-side validation).
- **Authorization:** protected route; the create/update calls also require a valid JWT server-side.

### Restaurant owner manages menu items
- **Start:** same form, "Menu" section.
- **Steps:** `MenuSection` uses a `useFieldArray` to add/remove `{ name, price }` rows; each row is validated (`name` required, `price` ≥ 1, coerced numeric) before the form can submit.
- **Screens involved:** `MenuSection`, `MenuItemInput`.
- **API calls:** none directly — submitted as part of the full restaurant create/update payload.
- **Success/loading/error/empty:** shared with the restaurant create/update flow above.
- **Authorization:** protected route.

### Restaurant owner views incoming orders
- **Start:** `/manage-restaurant` → "Orders" tab (paid and beyond) or "Orders Placed but Not Paid" tab (unpaid only).
- **Steps:** `EnhancedOrdersTab` renders stat tiles (total orders, revenue, average order, active orders), a search/status filter bar, a status-overview grid with progress bars, and per-date grouped order cards (grid or list view toggle).
- **Screens involved:** `ManageRestaurantPage`, `EnhancedOrdersTab`.
- **API calls:** `GET /api/my/restaurant/order` (polled every 5s while a restaurant exists).
- **Success state:** populated order cards.
- **Loading state:** plain "Loading orders..." text (no skeleton, unlike other list screens — CONFIRMED inconsistency, not a defect to silently "fix").
- **Empty state:** an empty `orders` array renders an empty grid with no explicit "no orders yet" message — **NEEDS CONFIRMATION** whether this is acceptable as-is.
- **Error state:** no distinct error UI is coded for a failed fetch.
- **Authorization:** protected route; server-side ownership check on the underlying data.

### Restaurant owner updates order status
- **Start:** the status `Select` dropdown on an order card in `EnhancedOrdersTab` (or the "Order Details" modal opened via "View Details").
- **Steps:** choosing a new status calls `useUpdateMyRestaurantOrder` → `PATCH /api/my/restaurant/order/:orderId/status` → on success, local state updates immediately and a status-change toast appears; the "placed" option is always disabled in the dropdown (an order can't be manually reverted to/left at "placed" via this control).
- **Screens involved:** `EnhancedOrdersTab`.
- **API calls:** `PATCH /api/my/restaurant/order/:orderId/status`.
- **Success state:** `showOrderStatusToast` (customer name, new status, order id).
- **Loading state:** the `Select` is `disabled` while the mutation is in flight.
- **Error state:** `showOrderErrorToast("Unable to update order status. Please try again.")`.
- **Authorization:** protected route; server-side ownership check (order's restaurant must belong to the caller).

### Restaurant owner views analytics, if present
- **Start:** "Business Insights" nav link → `/business-insights`.
- **Steps:** select a time range (7d/30d/90d/1y) → dashboard re-fetches.
- **Screens involved:** `AnalyticsDashboardPage`.
- **API calls:** `GET /api/business-insights` if logged in, `GET /api/business-insights/public` if not — **both call the identical backend handler and return identical data** (CONFIRMED, `CURRENT_STATE.md` §3/§8) — this is a **global** dashboard, not scoped to the viewer's own restaurant.
- **Success state:** stat tiles, top cities/cuisines, monthly trend, recent orders list.
- **Loading/empty/error states:** **NEEDS CONFIRMATION** — not inspected at the sub-component level in this pass; flagged for verification before Jira ticket estimation if precise behavior matters.
- **Authorization:** none — this page is intentionally public.

---

## 5. Current UI Component and Design Inventory

**Layout structure (CONFIRMED, `layouts/layout.tsx`):** a single `Layout` wrapper — `Header` → optional `Hero` (home page only) → `container mx-auto` content area → `Footer`. No sidebar exists anywhere in the app; `SearchPage` uses a two-column CSS grid (`250px` filter rail + flexible content), not a persistent sidebar.

**Header & navigation (CONFIRMED, `Header.tsx`, `MainNav.tsx`, `MobileNav.tsx`, `MobileNavLinks.tsx`, `UsernameMenu.tsx`):**
- Fixed-height (`72px`) header with a 2px orange bottom border; "BigHungers.com" wordmark (orange-500) links home.
- Desktop nav (`MainNav`, shown ≥ `md`): Restaurants, Order Status, Business Insights, Optimization, an "API" dropdown (API Docs, API Status), and an auth area (Log In button, or an avatar dropdown menu when signed in).
- Mobile nav (`MobileNav`, shown < `md`): a slide-out `Sheet` (right side) triggered by a hamburger icon, containing the same links plus a full-width Log In/avatar area.
- Avatar (`UsernameMenu`): shows the user's stored `image`, falling back to `https://robohash.org/<id>.png` (an external, unauthenticated third-party image service called directly from the browser — CONFIRMED, no backend involvement). Dropdown: Manage Restaurant, User Profile, Log Out.

**Sidebar:** none. (`SearchPage`'s cuisine filter column is the closest analog — a static-width grid column, not a collapsible sidebar.)

**Footer (CONFIRMED, `Footer.tsx`):** solid orange-500 band, wordmark + "Privacy Policy" / "Terms of Service" text. **These two are plain `<span>` elements with no `href` and no route — they are not functional links** (CONFIRMED). This is existing behavior, not something introduced by this analysis; it is noted so it is not mistaken for a regression during modernization testing.

**Buttons:** shadcn `Button` (`components/ui/button.tsx`) in `default`, `outline`, `ghost`, and `link` variants; the brand action color is `bg-orange-500` (hover `orange-600`), applied ad hoc via `className` rather than a themed "brand" variant.

**Forms:** `react-hook-form` + `zod` throughout, wrapped in shadcn's `Form`/`FormField`/`FormItem`/`FormMessage` primitives. Every form (`SearchBar`, `SignInPage`, `RegisterPage`, `UserProfileForm`, `ManageRestaurantForm`) follows the same field/label/inline-error pattern.

**Inputs:** shadcn `Input` (text, email, password, file). The restaurant image `Input` restricts file selection client-side to `.jpg, .jpeg, .png` via the `accept` attribute only — this is not a hard block, and the backend currently applies no file-type filter of its own (CONFIRMED, `CURRENT_STATE.md` §7).

**Tables:** no `<table>`-based data grids exist; list data (search results, orders, analytics) is rendered as stacked `Card` components instead.

**Cards:** shadcn `Card`/`CardHeader`/`CardTitle`/`CardContent`/`CardFooter` is the dominant layout primitive across search results, restaurant detail, order status, order management, analytics, API docs, and API status.

**Dialogs:** shadcn `Dialog` — used once, for the checkout delivery-details form (`CheckoutButton`). shadcn `Sheet` is used for the mobile nav drawer.

**Toasts:** `sonner`, mounted once in `main.tsx` (`<Toaster visibleToasts={1} position="bottom-right" richColors />`). Used for auth success/failure, restaurant create/update, order-status update, and a custom-styled payment-success toast on `OrderStatusPage`.

**Badges:** shadcn `Badge`, used for order status pills (color mapped per status via inline `getStatusColor` functions duplicated across `OrderStatusPage`, `EnhancedOrdersTab`, and `OrderItemCard` — the same color/icon mapping is copy-pasted in at least three places, CONFIRMED), API method tags on `ApiDocsPage`, and count badges.

**Status indicators:** `Progress` bars (order-status progress, analytics score bars, performance-metric bars); colored `Badge`s as above; `Skeleton` for loading placeholders.

**Typography:** Tailwind default stack (no custom font import found in `index.html`/`global.css` — **NEEDS CONFIRMATION** if a web font is loaded elsewhere); headings use `font-bold tracking-tight`/`tracking-tighter` utility combinations rather than a defined type scale.

**Spacing:** Tailwind spacing utilities (`gap-*`, `space-y-*`) throughout; a shared `container mx-auto` with `2rem` padding and a `1400px` max width at the `2xl` breakpoint (`tailwind.config.js`).

**Colors (CONFIRMED, `tailwind.config.js` + `global.css`):** the design system is shadcn/ui's "new-york" style on a `slate` base palette, driven by HSL CSS variables (`--background`, `--foreground`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--card`, `--popover`), with a `.dark` variant block already defined (though no runtime dark-mode toggle was found wired up in the app — **NEEDS CONFIRMATION**). The one consistent brand color used directly (not via a CSS variable) is Tailwind's `orange-500`/`orange-600`, applied throughout headers, primary buttons, and active/selected states.

**Responsive behavior:** Tailwind breakpoints (`md`, `lg`, `2xl`) drive: header nav collapse (`md`), search page column collapse (`lg`), analytics/orders grid column counts (`md`/`lg`), and image aspect-ratio layouts. No dedicated mobile-only screens exist — the same components reflow.

**Reusable components (non-exhaustive, confirmed present):** `SearchBar`, `CityDropdown`, `CuisineFilter`, `SortOptionDropdown`, `PaginationSelector`, `SearchResultCard`, `SearchResultInfo`, `MenuItem`, `OrderSummary`, `RestaurantInfo`, `CheckoutButton`, `LoadingButton`, `GlobalSpinner` (present in the tree but its usage site was not located in the pages inspected — **NEEDS CONFIRMATION**), `OrderStatusHeader`, `OrderStatusDetail`, `OrderRightColumn`, `OrderItemCard` (present in the component tree but not imported by any inspected page — **NEEDS CONFIRMATION** whether it is dead/superseded by `EnhancedOrdersTab`, which duplicates its layout), `EnhancedOrdersTab`, plus the full shadcn/ui primitive set in `components/ui/`.

We are **not** proposing a new design system. The existing shadcn/ui + Tailwind + CSS-variable setup is sufficient for a backend-only modernization.

---

## 6. Modernization Impact on the UI

| Area | Impact | Notes |
|---|---|---|
| API base URL | Small UI/API integration change | Only `VITE_API_BASE_URL` needs to point at the new FastAPI host; no frontend code references an Express-specific URL pattern. |
| Request/response format compatibility | Moderate UI change (risk area) | All 22 confirmed endpoints (`CURRENT_STATE.md` §3) must return the same JSON shapes the frontend already parses field-by-field (e.g., `res.data.token`, `res.data.user.email`, `results.pagination.total`). Any shape drift breaks the corresponding screen silently (React Query will just show `undefined` fields, not a crash, in most cases). |
| Authentication token handling | Small UI/API integration change | The frontend only needs `Authorization: Bearer <token>` support and the same JWT payload/expiry; the dead cookie fallback (`CURRENT_STATE.md` §5) needs no frontend accommodation either way. |
| Validation errors | Needs confirmation | The frontend does not currently branch its UI logic on the `{errors:[...]}` vs. `{message:[...]}` shape difference (`CURRENT_STATE.md` §9) — both are caught generically and shown as a single toast string. Low visual risk, but the exact resulting toast text will differ depending on which shape FastAPI returns; needs a decision (see `PRD.md` BM-04) before this is closed out. |
| HTTP status codes | Small UI/API integration change | The frontend checks `res.ok`/catches on non-2xx generically (`fetch`) or relies on axios throwing (interceptor has no custom status handling). As long as FastAPI returns the same status codes for the same conditions (e.g., 401 on bad auth, 409 on duplicate restaurant, 404 on not-found), no UI change is needed. |
| Pagination | No UI change | `RestaurantSearchResponse.pagination.{total,page,pages}` is the only shape `PaginationSelector`/`SearchResultInfo` read; preserve it exactly. |
| Search and filtering | Small UI/API integration change | Preserve `searchQuery`, `selectedCuisines` (comma-separated, AND semantics), `sortOption`, `page` query-param names and semantics. Note the confirmed frontend/backend mismatch below (§12) around the default `sortOption` value. |
| File uploads | Moderate UI change (risk area) | The restaurant image upload form posts `multipart/form-data` with a specific encoding: `imageFile` for the file, `cuisines[0]`, `cuisines[1]`... and `menuItems[0][name]`, `menuItems[0][price]`... for arrays (`ManageRestaurantForm.tsx` `onSubmit`). FastAPI's multipart parsing must accept this exact encoding, or the frontend's form-submission code must change — the latter is out of scope unless separately approved (`PRD.md` BM-05). |
| Stripe checkout integration | Small UI/API integration change | The frontend only needs `{ url }` back from `create-checkout-session` and performs a full-page redirect to it; no Stripe.js/Elements are embedded client-side. As long as FastAPI returns the same shape, no UI change is needed. |
| Order status updates | No UI change | The frontend polls `GET /api/order` / `GET /api/my/restaurant/order` every 5s and re-renders on data change; it does not care how the backend computes status, only that the same `status` enum values are returned. |
| Webhook-related status changes | No UI change | The webhook is server-to-server (Stripe → backend); the frontend only ever observes its effect via the next poll of `GET /api/order`. |
| Loading and error handling | Needs confirmation | Loading states already exist per-screen (see §4/§9) and are backend-agnostic. However, several screens (`SearchPage`, `DetailPage`, `EnhancedOrdersTab`) have **no explicit error UI today** for a failed request — this is an existing gap, not something the migration causes, but it becomes more visible risk during a backend swap because a misconfigured FastAPI deployment could fail silently from the user's point of view. Recommend explicitly deciding whether to close this gap as part of modernization (see §11 for scope boundary). |

---

## 7. Screen-by-Screen Change Specification

Only screens with a modernization-relevant dependency are listed. `Optimization` (`/optimization`) and `API Docs` (`/api-docs`, aside from its stale content, see §12) are excluded — they have no live backend dependency.

### Sign In (`/sign-in`)
- **Existing purpose:** password login, Google OAuth entry, seeded test-account picker.
- **Current behavior:** posts to `/api/auth/login`; stores JWT in `localStorage`; redirects to Google for OAuth.
- **Required modernization change:** none to the UI; FastAPI must accept the same `{ email, password }` body and return the same `{ userId, token, user: { id, email, name } }` shape.
- **Must remain unchanged:** form fields, test-account dropdown, Google button, toast copy.
- **May need modification:** none identified.
- **API contract dependency:** `POST /api/auth/login`, `GET /api/auth/google`.
- **Loading state:** button text "Signing in..." (exists).
- **Empty state:** N/A.
- **Error state:** toast with caught error message (exists).
- **Validation behavior:** client-side only (`required` on both fields); no field-level server-error mapping.
- **Authorization behavior:** none required to view.
- **Acceptance criteria:** Given valid credentials against the FastAPI backend, sign-in succeeds and behaves identically to today, including the test-account dropdown continuing to work with the seeded `test@user.com` account.
- **Priority:** High.
- **Related Jira issue type:** Story (under the Auth Compatibility epic-level work).

### Register (`/register`)
- **Existing purpose / behavior:** as documented in §4.
- **Required modernization change:** none to the UI; FastAPI must accept `{ email, password, name }` and return `{ token, userId, user }`.
- **Must remain unchanged:** all fields, toast copy, redirect-and-reload behavior.
- **API contract dependency:** `POST /api/auth/register`.
- **Loading/empty/error/validation/authorization:** as in §4.
- **Acceptance criteria:** duplicate-email registration still returns a 400 with a message the existing generic toast can display.
- **Priority:** High.
- **Related Jira issue type:** Story.

### Auth Callback (`/auth/callback`)
- **Required modernization change:** none to the UI; FastAPI's Google OAuth callback must redirect to `${FRONTEND_URL}/auth/callback` with the same query parameter names (`token`, `userId`, `email`, `name`, `image`, `error`).
- **Must remain unchanged:** the exact query parameter names read by `AuthCallbackPage.tsx`.
- **API contract dependency:** `GET /api/auth/callback/google` (server-side redirect target, not called by the frontend directly).
- **Acceptance criteria:** a successful Google sign-in lands the user on `/` fully authenticated, with the same `localStorage` keys populated as today.
- **Priority:** High.
- **Related Jira issue type:** Story.

### Search Results (`/search/:city`)
- **Required modernization change:** none to the UI; FastAPI must preserve `searchQuery`/`selectedCuisines`/`sortOption`/`page` semantics and the `{ data, pagination }` response shape.
- **Must remain unchanged:** filter rail, sort dropdown, pagination control, empty-state message.
- **May need modification:** none, **unless** the business decides to fix the `sortOption="bestMatch"` mismatch noted in §12 — that would be a backend-only fix with no frontend change required either way.
- **API contract dependency:** `GET /api/restaurant/search/:city`, `GET /api/restaurant/cities/all`.
- **Loading state:** 5 skeleton cards (exists).
- **Empty state:** "no restaurant near your search area" message (exists).
- **Error state:** none exists today — **do not add one unless separately approved**, per brownfield-minimal-change principle; flagged in §9 as a gap, not a requirement.
- **Acceptance criteria:** identical result sets, sort order, and pagination counts for the same query parameters against both backends.
- **Priority:** High.
- **Related Jira issue type:** Story.

### Restaurant Detail (`/detail/:restaurantId`)
- **Required modernization change:** none to the UI; FastAPI must preserve the restaurant JSON shape (including `menuItems[]._id` as a string comparable to what the cart stores).
- **Must remain unchanged:** menu list, cart behavior (client-side only), checkout dialog.
- **API contract dependency:** `GET /api/restaurant/:restaurantId`, `POST /api/order/checkout/create-checkout-session`.
- **Loading state:** full skeleton (exists).
- **Empty/error state:** none exists today for a missing/invalid restaurant ID — flagged as an existing gap, not to be silently introduced as a "fix" without approval.
- **Acceptance criteria:** adding items, adjusting quantity, and checking out produce the same Stripe redirect behavior as today.
- **Priority:** High.
- **Related Jira issue type:** Story.

### Order Status (`/order-status`)
- **Required modernization change:** none to the UI; FastAPI must preserve `GET /api/order`'s response shape and the order `status` enum values exactly.
- **Must remain unchanged:** date grouping, progress bar mapping, "Payment Required" banner logic, sign-in prompt for guests.
- **API contract dependency:** `GET /api/order`.
- **Loading state:** 2 skeleton order cards (exists).
- **Empty state:** "No Orders Found" message (exists).
- **Error state:** guest sign-in prompt (exists, but this is an auth-state branch, not an API-failure branch — no distinct API-error UI exists).
- **Acceptance criteria:** an order's status visibly advances on this page after the FastAPI webhook handler processes the same Stripe event.
- **Priority:** High.
- **Related Jira issue type:** Story.

### API Status (`/api-status`)
- **Existing purpose:** health dashboard.
- **Current behavior:** two real fetches (`/health`, `/api/business-insights/db-test`); three rows ("Payment Gateway", "File Storage", "Authentication") are **simulated** — their `status`/`responseTime` are derived from `Math.random()` and from whether the two real checks succeeded, not from actually contacting Stripe, Cloudinary, or an auth provider (CONFIRMED, `ApiStatusPage.tsx`).
- **Required modernization change:** none functionally required — the two real checks must keep working against the new `/health` and `/api/business-insights/db-test` FastAPI endpoints. **Do not represent the simulated rows as verifying real service health** in any Jira acceptance criteria; they don't today, and modernization does not need to make them real unless separately requested.
- **Must remain unchanged:** the page's visual layout and its two real checks.
- **May need modification:** the "Authentication" row's label references "Auth0" (CONFIRMED, `ApiStatusPage.tsx` line 85), which is not the app's actual authentication mechanism (JWT + Google OAuth) — see §12.
- **API contract dependency:** `GET /health`, `GET /api/business-insights/db-test`.
- **Acceptance criteria:** the "API Server" and "Database" rows correctly reflect the FastAPI backend's real health and MongoDB connectivity.
- **Priority:** Medium.
- **Related Jira issue type:** Story.

### Business Insights (`/business-insights`)
- **Required modernization change:** none to the UI; FastAPI must preserve the `AnalyticsData` response shape (`totalOrders`, `totalRevenue`, `averageOrderValue`, `totalCustomers`, `orderGrowth`, `revenueGrowth`, `topCities[]`, `topCuisines[]`, `recentOrders[]`, `monthlyData[]`).
- **Must remain unchanged:** the dashboard's global (not per-restaurant) scope, unless the business explicitly approves the scoping change flagged as an open question in `PRD.md`.
- **API contract dependency:** `GET /api/business-insights`, `GET /api/business-insights/public`.
- **Acceptance criteria:** identical figures returned for the same time range against both backends.
- **Priority:** Medium.
- **Related Jira issue type:** Story.

### User Profile (`/user-profile`)
- **Required modernization change:** none to the UI; FastAPI must preserve the `User` JSON shape and the `PUT` request body shape.
- **API contract dependency:** `GET /api/my/user`, `PUT /api/my/user`.
- **Loading state:** full skeleton form (exists).
- **Error state:** "Unable to load user profile" plain text (exists) — the only error-state text found in this pass that is a literal, un-styled fallback rather than a toast or card.
- **Acceptance criteria:** profile edits persist and are reflected on next load.
- **Priority:** Medium.
- **Related Jira issue type:** Story.

### Manage Restaurant (`/manage-restaurant`)
- **Required modernization change:** FastAPI's multipart parsing must accept the exact form-field encoding described in §6 (File Uploads row); price/array field names must match.
- **Must remain unchanged:** the three-tab layout, the pence/pounds display conversion (dividing by 100 for display, multiplying by 100 on submit), the disabled "placed" status option in the status selector, the 5s order polling.
- **May need modification:** none to the UI itself.
- **API contract dependency:** `GET /api/my/restaurant`, `POST /api/my/restaurant`, `PUT /api/my/restaurant`, `GET /api/my/restaurant/order`, `PATCH /api/my/restaurant/order/:orderId/status`.
- **Loading state:** "Loading orders..." plain text on the Orders tabs (exists, no skeleton — an existing inconsistency, not to be "fixed" without approval per brownfield principles).
- **Empty state:** no explicit "no orders" message exists for an empty order list — existing gap.
- **Error state:** none exists today for a failed orders fetch or a failed status update beyond the error toast on status-update failure.
- **Validation behavior:** zod schema on the restaurant form (client-side); server-side `express-validator` today, must be replicated with equivalent constraints in FastAPI (required strings, `deliveryPrice`/menu prices ≥ 0, non-empty `cuisines`/`menuItems`).
- **Authorization behavior:** protected route; server enforces per-request ownership on order-status updates.
- **Acceptance criteria:** creating a restaurant, editing it, uploading an image, adding/removing menu items, and updating an order's status all behave identically against FastAPI.
- **Priority:** High.
- **Related Jira issue type:** Story, with the image-upload and multipart-field-encoding piece broken out as a Sub-task given its higher integration risk.

---

## 8. API-to-UI Contract Handoff

Only endpoints actually called at runtime by a frontend screen are listed (the four unauthenticated analytics debug/test endpoints documented in `CURRENT_STATE.md` §3 are not called by any current screen and are therefore omitted here — they remain an open product question, see `PRD.md` §5).

| Frontend screen | Frontend action | Method | Existing endpoint | Expected request data | Expected response data | Auth required | Possible error responses | Required frontend handling | FastAPI migration notes | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Sign In | Submit login form | POST | `/api/auth/login` | `{ email, password }` | `{ userId, message, token, user:{id,email,name} }` | No | 400 (validation/invalid credentials), 500 | toast on error; store token on success | preserve field names exactly | CONFIRMED |
| Register | Submit register form | POST | `/api/auth/register` | `{ email, password, name }` | `201 { userId, token, user }` | No | 400 (validation/duplicate) | toast on error | preserve field names exactly | CONFIRMED |
| Sign In | "Continue with Google" | GET | `/api/auth/google` | — (full navigation) | 302 redirect to Google | No | 500 if OAuth not configured | none (browser follows redirect) | preserve redirect-based flow, not a JSON API | CONFIRMED |
| Auth Callback | (server redirect target) | GET | `/api/auth/callback/google` | — | 302 redirect to `/auth/callback?token=...` | No | redirects to `/sign-in?error=...` on failure | `AuthCallbackPage` reads query params | preserve exact query param names | CONFIRMED |
| All authenticated pages (via `AppContext`) | Background validation | GET | `/api/auth/validate-token` | Bearer token | `{ userId }` | Yes | 401 | drives `isLoggedIn` state | preserve shape | CONFIRMED |
| Header / avatar menu | "Log Out" | POST | `/api/auth/logout` | — | 200 empty body | No | — | clears `localStorage`, hard redirect to `/` | preserve as no-op-compatible; cookie clearing is not depended on by the frontend | CONFIRMED |
| User Profile / Checkout dialog | Load profile | GET | `/api/my/user` | Bearer token | `User` object | Yes | 404, 401 | `toast.error("Failed to fetch user")` on error | preserve `User` shape | CONFIRMED |
| User Profile | Save profile | PUT | `/api/my/user` | `{ name, addressLine1, city, country }` | updated `User` object | Yes | 400 (validation), 401, 404 | toast on error/success | preserve field names | CONFIRMED |
| Home / Search / City dropdown | Load city list | GET | `/api/restaurant/cities/all` | — | `{ cities: string[] }` | No | 500 | sets local error state (`useCitySearch`) | preserve shape | CONFIRMED |
| Search Results | Run search | GET | `/api/restaurant/search/:city` | query: `searchQuery, selectedCuisines, sortOption, page` | `{ data: Restaurant[], pagination:{total,page,pages} }` | No | 500 | none coded beyond `isLoading` | preserve query param names, AND-semantics for cuisines, ascending-only sort behavior unless changed by approval | CONFIRMED |
| Restaurant Detail | Load restaurant | GET | `/api/restaurant/:restaurantId` | — | `Restaurant` object | No | 400 (bad id), 404 | none coded | preserve `Restaurant` shape incl. `menuItems[]._id` as string | CONFIRMED |
| Restaurant Detail | Checkout | POST | `/api/order/checkout/create-checkout-session` | `{ cartItems, deliveryDetails, restaurantId }` | `{ url }` | Yes | 500 | toast on error; redirect on success | preserve pence-based totals, GBP currency, raw-body webhook prerequisite (see `PRD.md` BM-02) | CONFIRMED |
| (Stripe, not frontend-initiated) | Payment confirmation | POST | `/api/order/checkout/webhook` | raw Stripe event body + signature header | 200 empty | No (Stripe-signature verified) | 400 (bad signature) | none — frontend only sees the effect via the next `GET /api/order` poll | must preserve raw-body handling exactly | CONFIRMED |
| Order Status | Poll orders | GET | `/api/order` | Bearer token | `Order[]` | Yes | 500 | none coded beyond loading/empty states | preserve `Order` shape and `status` enum | CONFIRMED |
| Manage Restaurant | Load own restaurant | GET | `/api/my/restaurant` | Bearer token | `Restaurant \| null` | Yes | 500 | `restaurant` used to switch create/edit mode | preserve `null`-on-200 behavior for "no restaurant yet" | CONFIRMED |
| Manage Restaurant | Create restaurant | POST | `/api/my/restaurant` | `multipart/form-data` (see §6) | `201 Restaurant` | Yes | 409 (already exists), 400 (validation), 500 | toast on error/success | preserve multipart field encoding exactly | CONFIRMED |
| Manage Restaurant | Update restaurant | PUT | `/api/my/restaurant` | `multipart/form-data` | `200 Restaurant` | Yes | 400, 404, 500 | toast on error/success | preserve multipart field encoding exactly | CONFIRMED |
| Manage Restaurant | Load restaurant's orders | GET | `/api/my/restaurant/order` | Bearer token | `Order[]` | Yes | 500 | plain "Loading orders..." text; no error UI | preserve shape; includes unpaid `placed` orders | CONFIRMED |
| Manage Restaurant | Update order status | PATCH | `/api/my/restaurant/order/:orderId/status` | `{ status }` | `200 Order` | Yes | 400 (bad id), 401 (not owner), 404, 500 | success/error toast | preserve enum values and ownership-check semantics | CONFIRMED |
| Business Insights | Load analytics (authed) | GET | `/api/business-insights?timeRange=...` | Bearer token | `AnalyticsData` | Yes | 500 | none coded | preserve shape; currently identical to `/public` | CONFIRMED |
| Business Insights | Load analytics (guest) | GET | `/api/business-insights/public?timeRange=...` | — | `AnalyticsData` | No | 500 | none coded | preserve shape | CONFIRMED |
| API Status | Health check | GET | `/health` | — | `{ message, uptime, timestamp, serverStartTime }` | No | — | drives the "API Server" row | preserve shape, especially `uptime` (the frontend reads `healthData.uptime` directly) | CONFIRMED |
| API Status | DB check | GET | `/api/business-insights/db-test` | — | `{ message, orderCount, timestamp }` | No | 500 | drives the "Database" row | preserve shape | CONFIRMED |

---

## 9. Required UI States

The table below documents what already exists in code vs. what does not. **No state is claimed to exist unless it was found in source.**

| Screen | Initial loading | Submission loading | Empty | Validation error | API/server error | Unauthorized | Success feedback | Retry | Disabled controls during request |
|---|---|---|---|---|---|---|---|---|---|
| Sign In | N/A | Button text change (exists) | N/A | Inline `FormMessage` (client-side only, exists) | Toast (exists) | N/A | Toast + reload (exists) | None coded | Submit button (implied by `isLoading`, **needs confirmation** it's actually wired to `disabled`) |
| Register | N/A | `isLoading` state (exists) | N/A | Inline (exists) | Toast (exists) | N/A | Toast + reload (exists) | None coded | Not confirmed — **needs confirmation** |
| Search Results | Skeleton cards (exists) | N/A (no submit action beyond navigation) | Message (exists) | N/A | **Does not exist** | N/A | N/A | **Does not exist** | N/A |
| Restaurant Detail | Skeleton layout (exists) | `LoadingButton` on checkout dialog submit (exists) | Cart empty message (exists) | N/A | **Does not exist** for restaurant load | N/A | Toast on checkout error/success (exists) | **Does not exist** | Checkout button `disabled` when cart empty (exists) |
| Order Status | Skeleton cards (exists) | N/A | "No Orders Found" (exists) | N/A | **Does not exist** distinctly from empty | Sign-in prompt card (exists) | Payment-success toast (exists) | **Does not exist** | N/A |
| User Profile | Skeleton form (exists) | `isUpdateLoading` passed to form (exists) | "Unable to load user profile" text (exists, doubles as an error state) | Inline `FormMessage` (exists) | Same plain-text fallback as empty | N/A (protected route) | Toast (exists) | **Does not exist** | Not confirmed on form fields — **needs confirmation** |
| Manage Restaurant (form) | N/A (form pre-fills once restaurant loads) | `LoadingButton` (exists) | Blank one-row form for new owners (exists) | Inline `FormMessage` (exists) | Toast (exists) | N/A (protected route) | Toast (exists) | **Does not exist** | Not confirmed — **needs confirmation** |
| Manage Restaurant (orders) | Plain "Loading orders..." text (exists, no skeleton) | Status `Select` `disabled` while updating (exists) | **Does not exist** | N/A | **Does not exist** | N/A | Status-update toast (exists) | **Does not exist** | Status selector disabled during update (exists) |
| Business Insights | **Needs confirmation** (not inspected at sub-component level) | N/A | **Needs confirmation** | N/A | **Needs confirmation** | N/A (public page) | N/A | **Needs confirmation** | N/A |
| API Status | Initial fetch on mount, auto-refreshes every 30s (exists) | Refresh button spinner (exists) | N/A | N/A | Sets all rows to "error" status (exists) | N/A | N/A | Manual "Refresh" button (exists) | Refresh button `disabled` while checking (exists) |

Do not build out any "Does not exist" cell as part of the modernization unless it is separately approved — adding new error/retry states is scope expansion, not a compatibility requirement (see §11).

---

## 10. Responsive and Accessibility Requirements

These are implementation-quality floors for whatever frontend touch-ups are made during modernization (e.g., if a validation-error display needs adjusting) — **not a new visual design**.

- **Desktop (≥ 1024px / `lg`):** two-column layouts (search filter rail, restaurant detail menu/summary split, analytics grids) must continue to render as they do today.
- **Tablet (768–1023px / `md`):** header nav switches to the desktop `MainNav` at `md`; verify no horizontal overflow is introduced by any contract-driven UI change (e.g., a longer error message).
- **Mobile (< 768px):** header nav collapses to the `Sheet`-based `MobileNav`; single-column stacking for search, detail, and order screens (existing Tailwind responsive classes already do this — preserve them).
- **Keyboard navigation:** all interactive elements already use native `button`/`a`/`input` elements or Radix-based shadcn primitives (which have built-in keyboard support) — any new element introduced during this modernization (e.g., a new error-retry button, if approved) must be a real focusable, keyboard-operable control, not a `div` with an `onClick`.
- **Form labels:** every existing form field uses a shadcn `Label`/`FormLabel` — preserve this pattern for any new field.
- **Focus states:** the API dropdown trigger in `MainNav` already has an explicit visible focus ring (`focus:ring-2 focus:ring-orange-500`); apply the same visible-focus standard to any new interactive element.
- **Error messages:** existing inline `FormMessage` components are the pattern to reuse for any new validation-error text; do not introduce color-only error indication.
- **Button disabled states:** existing disabled buttons (`LoadingButton`, checkout button on empty cart, status selector during update) already show a visually distinct disabled state via shadcn's default styles — preserve this for any new disabled control.
- **Color contrast:** the existing orange-500-on-white and status-badge color combinations were not measured for WCAG contrast in this pass — **NEEDS CONFIRMATION** if this has been previously audited; no new low-contrast combination should be introduced by modernization work.
- **Screen-reader-friendly status messages:** toasts (`sonner`) are visual-only by default in this codebase — no `aria-live` region usage was found for toast announcements (**NEEDS CONFIRMATION**/existing gap, not to be silently fixed without approval, but worth flagging if any new status-communication UI is added during this project).

---

## 11. Out-of-Scope Changes

The following must **not** be performed during this modernization unless separately approved by the business/product owner:

- Complete visual redesign of any screen, component, or the shadcn/Tailwind design tokens.
- New business features not present in the current system.
- A new payment provider (Stripe stays).
- A new authentication provider (JWT + Google OAuth stays; "Auth0" references in `ApiStatusPage`/`.env.example` are stale documentation, not a live integration — see §12 — and do not imply Auth0 should be introduced).
- Major navigation restructuring (route list, header/mobile nav link set, and page hierarchy stay as-is).
- Changing order-status meanings or the five-value status enum.
- Changing database business rules (pence-based currency, cuisine AND-filter, one-restaurant-per-user, etc. — see `CURRENT_STATE.md` §8).
- Removing existing workflows without approval, including the currently-visible (if slightly unusual) elements such as the seeded test-account dropdown on Sign In, the hardcoded Stripe test-card notice on the checkout summary, or the "Orders Placed but Not Paid" tab.
- Silently "fixing" any of the existing gaps or inconsistencies documented in §9/§12 (missing error states, duplicated status-color logic, the `bestMatch` sort mismatch, the stale API docs) — each requires an explicit decision, not a default engineering choice, per `BUSINESS_PROBLEM_STATEMENT.md` and `PRD.md`.

---

## 12. Open Questions and Risks

1. **`ApiDocsPage.tsx` documents an endpoint that does not exist.** It lists `POST /api/order/checkout` ("Create a new order") — the real backend only exposes `POST /api/order/checkout/create-checkout-session` and `POST /api/order/checkout/webhook` (CONFIRMED against `routes/OrderRoute.ts`). This stale documentation should not be used as a reference by the modernization team, and its correction (or removal) is a candidate Jira item — **needs a decision** on whether to fix it as part of this project or leave it (it is user-facing but non-functional, i.e., text only).
2. **`ApiStatusPage.tsx` simulates three of its five "service" rows.** "Payment Gateway" (Stripe), "File Storage" (Cloudinary), and "Authentication" (labeled "Auth0") never make a real network call to those services — their status/response-time values are derived from `Math.random()` and from the two real checks. **Do not treat this page as evidence that Stripe/Cloudinary/Google OAuth are configured or working** — that must be verified separately (env vars present and valid), and this page's simulated rows should not be relied on for go-live sign-off.
3. **The "Authentication" row is mislabeled "Auth0".** The app does not use Auth0 (CONFIRMED — JWT + server-side Google OAuth is the real mechanism, `CURRENT_STATE.md` §5). This is consistent with the stale `VITE_AUTH0_*` variables in `food-ordering-frontend/.env.example` (`CURRENT_STATE.md` §1) — both point to leftover artifacts from an earlier architecture. **Needs a decision** on whether to correct the label as part of this project.
4. **`SearchPage`'s default `sortOption` is `"bestMatch"`, but the backend has no such field** on the `Restaurant` model (`CURRENT_STATE.md` §4 lists `restaurantName, city, country, deliveryPrice, estimatedDeliveryTime, cuisines, menuItems, imageUrl, lastUpdated` — no `bestMatch`). Sorting by a non-existent field is effectively a no-op in MongoDB, so the default "Best match" sort likely returns results in an arbitrary/insertion order rather than any meaningful ranking. **Needs confirmation** whether this is an accepted long-standing quirk or something the business wants addressed (and if so, whether that's in scope for this modernization or a separate product change).
5. Every open question already carried from `BUSINESS_PROBLEM_STATEMENT.md`/`PRD.md` remains unresolved and applies here too: production deployment target (Render/Netlify vs. Coolify), analytics global-vs-scoped decision, disposition of the debug/test analytics endpoints, the dead cookie/`state`-param anomalies, and the dropped delivery `country` field.
6. **Missing environment variables for full verification:** this analysis did not have access to live `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `CLOUDINARY_*`, `GOOGLE_ID`/`GOOGLE_SECRET`, or a reachable `MONGODB_URI` — no claim is made here that any of these external services are currently configured correctly or reachable; that must be verified against the actual deployment environment before cutover.
7. **Compatibility risk — multipart form encoding.** The restaurant create/update form's array-field encoding (`cuisines[0]`, `menuItems[0][name]`) is a specific convention that not every server-side multipart parser handles identically out of the box; this is the single highest-risk UI-facing integration point for the FastAPI port (also flagged in `PRD.md` BM-05).
8. **`OrderItemCard.tsx` and `GlobalSpinner.tsx` appear unused by any currently-routed page** in this pass — **needs confirmation** whether they are dead code (candidates for removal in a future, separately-scoped cleanup) or used somewhere not covered by this inspection.

---

## 13. Jira-Ready Work Items

Grouped under one epic. No issue keys are invented — these are ready to paste into Jira as new issues, to be assigned real keys at creation time.

**Epic: Backend Modernization — Node.js/Express → Python/FastAPI (UI Compatibility Track)**
Description: Ensure the existing BigHungers frontend continues to function without required code changes once its backend is replaced with FastAPI, per `BROWNFIELD_UI_UX_HANDOFF.md`, `PRD.md`, and `BRD.md`.

| Issue type | Summary | Description | Acceptance criteria | Priority | Dependencies | Related screen/workflow | Technical notes |
|---|---|---|---|---|---|---|---|
| Story | Confirm and freeze API contract inventory | Validate every row in §8 against the actual FastAPI implementation plan before coding begins. | All 22 endpoint contracts signed off by engineering and product; deviations logged as separate decisions. | Highest | None | All | Source of truth: §8 of this document, `CURRENT_STATE.md` §3. |
| Story | Auth compatibility: password + JWT | FastAPI implements `/api/auth/register`, `/login`, `/validate-token`, `/logout` with identical request/response shapes and JWT payload. | Sign-in/register/logout journeys in §4 pass unchanged against FastAPI. | Highest | API contract freeze | Sign In, Register | Preserve `{userId}` JWT payload, 1-day expiry, bcrypt-equivalent hashing. |
| Story | Auth compatibility: Google OAuth | FastAPI implements `/api/auth/google` and `/api/auth/callback/google` with the same redirect-based flow and query parameter names. | "Customer signs in with Google" journey in §4 passes unchanged. | High | API contract freeze | Sign In, Auth Callback | Decide open question on `state` param validation (§12) before closing. |
| Story | Restaurant & menu management APIs | FastAPI implements `GET/POST/PUT /api/my/restaurant` with identical multipart form encoding and pence-conversion rules. | Create/update restaurant and menu items via the existing form succeeds identically. | Highest | API contract freeze | Manage Restaurant | Highest-risk item — see §12 point 7. |
| Sub-task | Multipart form-field encoding verification | Specifically verify `cuisines[n]` and `menuItems[n][name/price]` parsing under FastAPI. | A submitted form with 3+ cuisines and 3+ menu items round-trips correctly. | Highest | Restaurant & menu management APIs story | Manage Restaurant | See `PRD.md` BM-05. |
| Story | Restaurant discovery & search APIs | FastAPI implements `GET /api/restaurant/cities/all`, `/:restaurantId`, `/search/:city` with identical query semantics and response shape. | Search Results and Restaurant Detail journeys in §4 pass unchanged, including AND cuisine filtering and fixed page size of 10. | High | API contract freeze | Home, Search Results, Restaurant Detail | Decide whether to fix the `bestMatch` sort mismatch (§12 point 4) — default: preserve as-is. |
| Story | Order & checkout/payment APIs | FastAPI implements `GET /api/order`, `POST /checkout/create-checkout-session`, `POST /checkout/webhook` with raw-body signature verification preserved. | Full checkout journey (§4) completes and order status updates to "paid" after webhook processing. | Highest | API contract freeze | Restaurant Detail (checkout), Order Status | See `PRD.md` BM-02 for raw-body requirement. |
| Story | Restaurant order management APIs | FastAPI implements `GET /api/my/restaurant/order` and `PATCH .../:orderId/status` with identical ownership checks and status enum. | Restaurant-owner order view and status-update journeys in §4 pass unchanged. | High | API contract freeze | Manage Restaurant (orders) | Preserve disabled "placed" option behavior client-side (no change needed — already client-only). |
| Story | Business insights API | FastAPI implements `GET /api/business-insights` and `/public` returning identical `AnalyticsData` shape. | Business Insights dashboard renders identical figures for the same time range. | Medium | API contract freeze | Business Insights | Global-scope-vs-owner-scope open question must be resolved first if changing; default is preserve as global. |
| Story | Health/status endpoints | FastAPI implements `/`, `/health`, `/api/health`, `/api/business-insights/db-test` with identical response shapes. | API Status page's two real checks report correctly against FastAPI. | Medium | API contract freeze | API Status | Do not extend the simulated rows as part of this story (§12 point 2). |
| Story | Regression test pass across all screens | Manually (or via new automated tests) walk every journey in §4 against the FastAPI backend. | Every journey's success/loading/empty/error state (as it exists today, per §9) behaves identically. | Highest | All API stories above | All | This is also the primary vehicle for establishing the automated test baseline required by `BRD.md`/`PRD.md`. |
| Story (optional, needs product approval) | Correct stale API documentation | Update or remove the incorrect `POST /api/order/checkout` entry in `ApiDocsPage.tsx` and the "Auth0" mislabel in `ApiStatusPage.tsx`. | `ApiDocsPage` lists only real endpoints; `ApiStatusPage` labels reflect the actual auth mechanism. | Low | None | API Docs, API Status | Frontend-only text change; confirm with product before doing this, since it is technically a frontend code change (see brownfield principle on minimal frontend changes). |

## 14. Final Implementation Guidance

**Recommended order of implementation:**

1. **Backend API contract confirmation** — freeze the request/response shape for all 22 endpoints against §8 of this document before writing any FastAPI code.
2. **Authentication compatibility** — password login/register and Google OAuth, since every other authenticated screen depends on it.
3. **Restaurant and menu APIs** — including the multipart form-encoding verification, the single highest UI-integration risk area.
4. **Search and restaurant details** — public, unauthenticated read paths; lower risk, good early confidence-builder.
5. **Order and checkout APIs** — including the raw-body Stripe webhook requirement, the most business-critical path.
6. **Restaurant order management** — depends on both auth and order APIs being stable.
7. **Error/loading/empty states** — verify the *existing* states in §9 still trigger correctly; do not add new ones without approval.
8. **Regression testing** — walk every journey in §4 end-to-end against the FastAPI backend before cutover.

### Confirmed facts
- All 13 routes, their components, and their API dependencies listed in §3 and §8.
- The multipart form-field encoding used by the restaurant management form.
- The two real vs. three simulated checks on `ApiStatusPage`.
- The incorrect endpoint documented on `ApiDocsPage`.
- The absence of dedicated error-state UI on several list/detail screens (Search Results, Restaurant Detail, Order Status API-failure case, Manage Restaurant orders).

### Assumptions
- That the organization's decision to move to FastAPI is independent of any UI defect (per `BUSINESS_PROBLEM_STATEMENT.md`).
- That no visual/design refresh is desired alongside this backend migration.
- That the seeded test account, dummy Stripe test-card notice, and other demo-oriented UI text are intentionally still present for a non-production/staging use case (not verified against a specific environment).

### Needs human confirmation
- Whether `OrderItemCard.tsx` and `GlobalSpinner.tsx` are dead code or used in a path not covered by this inspection.
- Whether dark mode (CSS variables already defined) is actually reachable via any UI control.
- Whether the `bestMatch` sort mismatch, the `ApiDocsPage` error, and the "Auth0" mislabel should be corrected as part of this modernization or left untouched.
- The loading/empty/error state behavior of the Business Insights dashboard at the sub-component level.
- Live configuration status of Stripe, Cloudinary, and Google OAuth credentials in the target deployment environment.

### Recommended next step
Convert §13's Jira-ready items into real Jira issues under a newly created (or existing) "Backend Modernization" epic, starting with the "Confirm and freeze API contract inventory" story — every other story depends on it.
