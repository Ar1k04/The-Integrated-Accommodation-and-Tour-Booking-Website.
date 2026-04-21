# Project Structure

## Root

| File | Description |
|---|---|
| `.env` | Environment variables (secrets, DB credentials, API keys) — not committed |
| `.env.example` | Template with all required env vars: Postgres, Redis, JWT, Stripe, Cloudinary, SMTP, frontend URL |
| `.gitignore` | Ignores `.env`, `node_modules/`, `__pycache__/`, `dist/`, `Instruction/`, `.agents/`, IDE/OS files |
| `docker-compose.yml` | Orchestrates 5 services: **postgres** (15-alpine), **redis** (7-alpine), **backend** (FastAPI), **frontend** (Vite React), **pgadmin**. Uses health checks, named volumes, and a bridge network |
| `skills-lock.json` | Lock file for Cursor agent skills |

---

## Instruction/

| File | Description |
|---|---|
| `CODEBASE_REVIEW.md` | Codebase review notes |
| `Files.md` | This file — full project structure documentation |
| `RUN_WEBSITE.md` | Instructions for running the project locally |
| `memory.md` | Project memory/context notes |

---

## Backend (`backend/`)

### Config & Build

| File | Description |
|---|---|
| `Dockerfile` | Python 3.11-slim image, installs gcc + libpq-dev, pip installs requirements, runs uvicorn with `--reload` on port 8000 |
| `alembic.ini` | Alembic configuration — points to `alembic/` directory, logging config for SQLAlchemy/Alembic |
| `pytest.ini` | Pytest config — `asyncio_mode = auto`, test discovery in `tests/` for `test_*.py` files |
| `requirements.txt` | Python dependencies: FastAPI 0.110, SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, python-jose (JWT), bcrypt, Stripe, Redis, Cloudinary, slowapi (rate limiting), aiosmtplib, httpx, Jinja2. Testing: pytest, pytest-asyncio, aiosqlite |

### Alembic (Database Migrations)

| File | Description |
|---|---|
| `alembic/env.py` | Async migration runner — imports all models to populate `Base.metadata`, overrides DB URL from `settings.DATABASE_URL`, supports both offline and online (async) migration modes |
| `alembic/script.py.mako` | Mako template for generating new migration revision files |
| `alembic/versions/` | Auto-generated migration files (per revision) |

### App Entry Point

| File | Description |
|---|---|
| `app/__init__.py` | Package marker |
| `app/main.py` | FastAPI application factory. Sets up: Redis connection via lifespan, CORS middleware (allows frontend origin), rate-limit error handler, global exception handler (500). Registers 11 routers under `/api/v1`. Exposes `/health` endpoint |

### Core (`app/core/`)

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `config.py` | `Settings` class using `pydantic-settings` — loads from `.env`. Fields: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` (15), `REFRESH_TOKEN_EXPIRE_DAYS` (7), Stripe keys, Cloudinary credentials, email config, `FRONTEND_URL` |
| `security.py` | Password hashing with bcrypt (SHA-256 pre-hash for arbitrary-length passwords). JWT creation: `create_access_token` (15 min), `create_refresh_token` (7 days, includes `jti` for blacklisting). `decode_token` with error handling |
| `dependencies.py` | FastAPI dependencies: `get_current_user` — extracts user from Bearer header or `access_token` cookie, validates access token, checks user exists and is active. `require_admin` — verifies `role == "admin"`. Exports `CurrentUser` and `AdminUser` annotated types |

### Database (`app/db/`)

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `base.py` | SQLAlchemy `DeclarativeBase` with common columns: `id` (UUID, auto-generated), `created_at` (timestamp with timezone, server default `now()`), `updated_at` (auto-updates on change) |
| `session.py` | Creates async engine from `DATABASE_URL` with `pool_pre_ping`. Provides `get_db` generator: yields `AsyncSession`, auto-commits on success, rollbacks on exception |

### Models (`app/models/`)

| File | Description |
|---|---|
| `__init__.py` | Re-exports all models and enums: `User`, `UserRole`, `Hotel`, `Room`, `Booking`, `BookingStatus`, `Tour`, `TourBooking`, `TourBookingStatus`, `Review`, `Payment`, `PaymentStatus`, `Wishlist`, `PromoCode` |
| `user.py` | **User** model — `users` table. Fields: `email` (unique, indexed), `hashed_password`, `full_name`, `phone`, `avatar_url`, `role` (user/admin), `is_active`, `loyalty_points`. Relationships: bookings, tour_bookings, reviews, wishlists |
| `hotel.py` | **Hotel** model — `hotels` table. Fields: `name`, `slug` (unique, indexed), `description`, `address`, `city` (indexed), `country` (indexed), `latitude/longitude`, `star_rating` (1-5), `property_type`, `amenities` (JSONB), `images` (JSONB), `base_price`, `currency`, `avg_rating`, `total_reviews`. Relationships: rooms (cascade delete), reviews |
| `room.py` | **Room** model — `rooms` table. FK to `hotels`. Fields: `name`, `description`, `room_type`, `price_per_night`, `total_quantity` (inventory count), `max_guests`, `amenities` (JSONB), `images` (JSONB). Relationships: hotel, bookings |
| `booking.py` | **Booking** model — `bookings` table. FKs to `users`, `rooms`, optional FK to `promo_codes`. Fields: `check_in`, `check_out` (Date, indexed), `guests_count`, `total_price`, `status` (pending/confirmed/cancelled/completed), `special_requests`. Relationships: user, room, payment (one-to-one) |
| `tour.py` | **Tour** model — `tours` table. Fields: `name`, `slug` (unique), `description`, `city`, `country`, `category`, `duration_days`, `max_participants`, `price_per_person`, `highlights` (JSONB), `itinerary` (JSONB), `includes` (JSONB), `excludes` (JSONB), `images` (JSONB), `avg_rating`, `total_reviews`. Relationships: tour_bookings, reviews |
| `tour_booking.py` | **TourBooking** model — `tour_bookings` table. FKs to `users`, `tours`. Fields: `tour_date`, `participants_count`, `total_price`, `status` (pending/confirmed/cancelled/completed), `special_requests`. Relationships: user, tour |
| `review.py` | **Review** model — `reviews` table. FKs to `users`, optional FKs to `hotels` and `tours`. Check constraint: exactly one of `hotel_id` or `tour_id` must be set. Fields: `rating` (int), `comment`. Relationships: user, hotel, tour |
| `payment.py` | **Payment** model — `payments` table. Optional FK to `bookings`. Fields: `stripe_payment_intent_id` (unique), `amount`, `currency`, `status` (pending/succeeded/failed/refunded). Relationship: booking |
| `wishlist.py` | **Wishlist** model — `wishlists` table. FK to `users`, optional FKs to `hotels` and `tours`. Check constraint: exactly one of `hotel_id` or `tour_id` must be set. Relationships: user, hotel (selectin), tour (selectin) |
| `promo_code.py` | **PromoCode** model — `promo_codes` table. Fields: `code` (unique, indexed), `discount_percent`, `max_uses`, `current_uses`, `min_booking_amount`, `is_active`, `expires_at` |

### Schemas (`app/schemas/`)

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `auth.py` | Pydantic models: `LoginRequest` (email + password), `TokenResponse` (access_token + token_type), `ForgotPasswordRequest`, `ResetPasswordRequest` (token + new_password, min 8 chars), `ChangePasswordRequest` |
| `user.py` | `UserCreate` (email, password 8-1024 chars, full_name, phone, role), `UserUpdate` (partial: full_name, phone, avatar_url, role, is_active), `UserResponse` (full user fields + timestamps, `from_attributes`), `UserListResponse` (items + meta) |
| `hotel.py` | `HotelCreate` (all hotel fields with validation), `HotelUpdate` (all optional), `HotelResponse` (full hotel output + timestamps), `HotelListResponse` (paginated) |
| `room.py` | `RoomCreate`, `RoomUpdate`, `RoomResponse`, `RoomListResponse`, `RoomAvailabilityResponse` (available bool + rooms_left count) |
| `booking.py` | `BookingCreate` (room_id, dates, guests_count, special_requests, promo_code), `BookingUpdate` (guests_count, special_requests), `BookingResponse`, `BookingDetailResponse` (extends BookingResponse with nested `RoomResponse`), `BookingListResponse` |
| `tour.py` | `TourCreate` (with highlights, itinerary, includes, excludes), `TourUpdate`, `TourResponse`, `TourListResponse` |
| `tour_booking.py` | `TourBookingCreate` (tour_id, tour_date, participants_count), `TourBookingUpdate`, `TourBookingResponse`, `TourBookingListResponse` |
| `review.py` | `ReviewCreate` (hotel_id or tour_id, rating 1-5, comment), `ReviewUpdate`, `ReviewResponse` (includes nested `UserResponse`), `ReviewListResponse` |
| `payment.py` | `PaymentCreate` (booking_id, amount, currency), `PaymentResponse` (includes stripe_payment_intent_id, status) |
| `wishlist.py` | `WishlistCreate` (hotel_id or tour_id), `WishlistResponse`, `WishlistListResponse` |
| `promo_code.py` | `PromoCodeCreate`, `PromoCodeUpdate`, `PromoCodeResponse`, `PromoCodeValidateResponse` (valid bool, discount_percent, message) |
| `common.py` | Reusable schemas: `PaginationMeta` (total, page, per_page, total_pages), `ListResponse`, `MessageResponse` |

### API Routes (`app/api/v1/routes/`)

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `auth.py` | **Auth endpoints** (`/api/v1/auth`): `POST /register` (rate-limited 5/min, returns tokens, sets refresh cookie), `POST /login` (rate-limited 5/min), `POST /logout` (blacklists refresh token in Redis, clears cookie), `POST /token/refresh` (rotation: blacklists old token, issues new pair), `POST /password/forgot` (sends reset email in background), `POST /password/reset`, `GET /me` (returns current user), `PATCH /me` (update profile) |
| `hotels.py` | **Hotel CRUD** (`/api/v1/hotels`): `GET /` (paginated list with filters: city, country, check_in/check_out availability, guests, price range, star_rating, amenities, property_type, text search, sorting), `GET /{id}`, `POST /` (create, requires auth), `PUT /{id}` (full replace), `PATCH /{id}` (partial update), `DELETE /{id}`, `POST /{id}/images` (Cloudinary upload) |
| `rooms.py` | **Room CRUD** (`/api/v1`): `GET /hotels/{hotel_id}/rooms` (with date-based availability filtering), `POST /hotels/{hotel_id}/rooms`, `GET /rooms/{id}`, `PUT /rooms/{id}`, `PATCH /rooms/{id}`, `DELETE /rooms/{id}`, `GET /rooms/{id}/availability` (returns available bool + rooms_left), `POST /rooms/{id}/images` |
| `bookings.py` | **Booking CRUD** (`/api/v1/bookings`): `POST /` (creates booking via `check_and_reserve` with row-level locking), `GET /` (user's bookings, filterable by status), `GET /{id}` (detail with room info), `PATCH /{id}` (update if not cancelled/completed), `DELETE /{id}` (sets status to cancelled) |
| `tours.py` | **Tour CRUD** (`/api/v1/tours`): `GET /` (paginated with filters: city, country, category, text search, price range, duration, sorting), `GET /{id}`, `POST /`, `PUT /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/images` |
| `tour_bookings.py` | **Tour Booking CRUD** (`/api/v1/tour-bookings`): `POST /` (checks participant capacity with `FOR UPDATE` lock, calculates total price), `GET /` (user's tour bookings), `GET /{id}`, `PATCH /{id}` (recalculates price on participant change), `DELETE /{id}` (cancels) |
| `reviews.py` | **Review CRUD** (`/api/v1`): `GET /hotels/{id}/reviews` (paginated, sortable by recent/rating), `GET /tours/{id}/reviews`, `POST /reviews` (requires completed booking for hotel or tour, one review per entity per user), `PATCH /reviews/{id}` (owner only), `DELETE /reviews/{id}` (owner or admin). Auto-updates `avg_rating` and `total_reviews` on parent entity |
| `payments.py` | **Payment endpoints** (`/api/v1/payments`): `POST /` (creates Stripe PaymentIntent, returns client_secret), `GET /{id}`, `POST /webhooks` (Stripe webhook handler: verifies signature, processes `payment_intent.succeeded` / `payment_intent.payment_failed`), `DELETE /{id}` (refund via Stripe) |
| `wishlists.py` | **Wishlist CRUD** (`/api/v1/wishlists`): `GET /` (user's wishlist, paginated), `POST /` (add hotel or tour, prevents duplicates), `DELETE /{id}` |
| `promo_codes.py` | **Promo Code CRUD** (`/api/v1/promo-codes`): `POST /validate` (checks code validity, expiry, usage limit, min booking amount), `POST /`, `GET /` (paginated list), `PATCH /{id}`, `DELETE /{id}` |
| `admin.py` | **Admin endpoints** (`/api/v1/admin`, requires admin role): `GET /stats` (dashboard: total revenue, bookings count, occupancy rate, new users, revenue chart data, bookings by status, recent bookings — filterable by week/month/year), `GET /users` (searchable, paginated), `GET /users/{id}`, `PATCH /users/{id}`, `DELETE /users/{id}`, `GET /bookings` (all bookings, filterable), `PATCH /bookings/{id}` (update status) |

### Services (`app/services/`)

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `auth_service.py` | Business logic: `register_user` (checks email uniqueness, hashes password), `authenticate_user` (verifies credentials + active status), `issue_tokens` (access + refresh pair), `blacklist_token` / `is_token_blacklisted` (Redis-backed), `validate_refresh_token` (decodes, checks type + blacklist), `create_password_reset_token` (1-hour expiry), `verify_password_reset_token`, `reset_user_password` |
| `availability_service.py` | `check_and_reserve` — atomic booking with `SELECT ... FOR UPDATE` on Room row. Validates dates, guest count, checks overlapping bookings against `total_quantity`. Calculates price (nights × price_per_night), optionally applies promo code discount. Returns created Booking |
| `cloudinary_service.py` | Cloudinary integration: `upload_image` (single file upload, returns secure URL), `upload_images` (batch upload). Configured from `settings` |
| `payment_service.py` | Stripe integration: `create_payment_intent` (creates PaymentIntent with booking metadata, stores local Payment record), `handle_webhook_event` (processes succeeded/failed events, confirms bookings, awards loyalty points at $1/point), `refund_payment` (full Stripe refund, cancels booking) |

### Tests (`backend/tests/`)

| File | Description |
|---|---|
| `__init__.py` | Package marker |
| `conftest.py` | Pytest fixtures: in-memory SQLite via aiosqlite (no Postgres/Redis needed), `setup_db` (creates/drops tables per test), `db_session`, `client` (httpx AsyncClient with ASGI transport, mock Redis), `test_user`, `admin_user`, `user_token`, `admin_token`, `test_hotel`, `test_room`, `auth_header` helper |
| `test_auth.py` | 9 tests: health check, register (success + duplicate), login (success + wrong password), get me (authenticated + unauthenticated), update profile, logout |
| `test_bookings.py` | 7 tests: create booking (success + invalid dates + too many guests + unauthenticated), list bookings, double-booking prevention (books all quantity then verifies rejection), cancel booking |
| `test_hotels.py` | 7 tests: list hotels, get hotel (found + not found), create hotel (admin + non-admin role check), search by city, delete hotel |

---

## Frontend (`frontend/`)

### Config & Build

| File | Description |
|---|---|
| `.env` / `.env.example` | Frontend environment variables (e.g., `VITE_API_BASE_URL`) |
| `.gitignore` | Ignores `node_modules/`, `dist/`, env files |
| `Dockerfile` | Node 20-alpine image, npm install, runs `npm run dev` with `--host 0.0.0.0` on port 5173 |
| `package.json` | **Dependencies**: React 19, React Router v7, TanStack React Query v5, Zustand v5, Axios, Tailwind CSS v4, Framer Motion, Lucide icons, Recharts, Leaflet maps, Stripe.js, date-fns, sonner (toasts), clsx + tailwind-merge, jsPDF, react-helmet-async. **Dev**: Vite 8, Vitest 4, Testing Library (React + jest-dom), ESLint |
| `eslint.config.js` | Flat ESLint config: JS/JSX files, React hooks + React Refresh rules, unused vars ignored if uppercase/underscore pattern |
| `vite.config.js` | Vite config: React plugin, Tailwind CSS v4 plugin, `@` alias to `./src`, dev server on `0.0.0.0:5173` with `/api` proxy to `localhost:8000`, Vitest setup with jsdom |
| `index.html` | HTML entry point — title "TravelBooking", SEO meta description, theme-color `#003580` |
| `README.md` | Frontend README |

### Public Assets

| File | Description |
|---|---|
| `public/favicon.svg` | Site favicon |
| `public/icons.svg` | SVG sprite for shared icons |

### Source Entry

| File | Description |
|---|---|
| `src/main.jsx` | App bootstrap: wraps in `StrictMode`, `HelmetProvider`, `QueryClientProvider` (5-min stale time, 1 retry, no refetch on focus), `RouterProvider`. Calls `useAuthStore.initialize()` to attempt token refresh on load |
| `src/App.jsx` | Default Vite starter component (unused — routing takes over via `main.jsx`) |
| `src/App.css` | Default Vite starter styles |
| `src/index.css` | Global Tailwind CSS styles and custom design tokens |

### API Layer (`src/api/`)

| File | Description |
|---|---|
| `axiosInstance.js` | Shared Axios instance: base URL from `VITE_API_BASE_URL` or `/api/v1`, `withCredentials: true`. **Request interceptor**: attaches Bearer token from auth store. **Response interceptor**: on 401, queues failed requests, attempts silent token refresh, replays queued requests on success |
| `authApi.js` | Auth API methods: `register`, `login`, `logout`, `refreshToken`, `forgotPassword`, `resetPassword`, `getMe`, `updateMe`, `changePassword` |
| `hotelsApi.js` | Hotel API methods: `list` (with params), `get`, `create`, `update`, `replace`, `delete`, `uploadImages` (multipart/form-data) |
| `roomsApi.js` | Room API methods: `listByHotel`, `get`, `create`, `update`, `delete`, `checkAvailability` |
| `bookingsApi.js` | Booking API methods: `list`, `get`, `create`, `update`, `cancel` |
| `toursApi.js` | Tour + Tour Booking API methods: `list`, `get`, `create`, `update`, `delete`, `listBookings`, `getBooking`, `createBooking`, `updateBooking`, `cancelBooking` |
| `paymentsApi.js` | Payment API methods: `create`, `get`, `refund` |
| `reviewsApi.js` | Review API methods: `listHotelReviews`, `listTourReviews`, `create`, `update`, `delete` |
| `adminApi.js` | Admin API methods: `getStats`, `listUsers`, `getUser`, `updateUser`, `deleteUser`, `listBookings`, `updateBooking`, promo code CRUD (`listPromoCodes`, `createPromoCode`, `updatePromoCode`, `deletePromoCode`, `validatePromoCode`), wishlist management (`listWishlists`, `addToWishlist`, `removeFromWishlist`) |

### State Management (`src/store/`)

| File | Description |
|---|---|
| `authStore.js` | Zustand store for authentication. State: `user`, `accessToken`, `isAuthenticated`, `isLoading`. Actions: `login` (authenticate + fetch profile), `register`, `logout` (calls API + clears state), `refreshToken` (silent refresh via cookie, fetches user), `updateProfile`, `initialize` (called on app boot to restore session) |
| `bookingStore.js` | Zustand store for booking flow. State: `selectedRoom`, `hotel`, `checkIn`, `checkOut`, `guests`, `promoCode`, `discount`. Actions: `setBookingData`, `applyPromo`, `clearBooking` |
| `searchStore.js` | Zustand store for search state. State: `destination`, `checkIn`, `checkOut`, `guests` (adults/children/rooms), `searchType` (hotels/tours). Actions: `setDestination`, `setDates`, `setGuests`, `setSearchType`, `resetSearch` |

### Hooks (`src/hooks/`)

| File | Description |
|---|---|
| `useAuth.js` | Convenience hook — selects individual auth store fields to avoid unnecessary re-renders. Returns: `user`, `isAuthenticated`, `isLoading`, `isAdmin`, `login`, `logout`, `register`, `refreshToken`, `updateProfile` |
| `useDebounce.js` | Generic debounce hook — delays value updates by configurable delay (default 300ms). Used for search input |
| `useInfiniteScroll.js` | IntersectionObserver-based infinite scroll hook — returns a `ref` callback to attach to the last element. Triggers `callback` when element enters viewport. Configurable `threshold` and `enabled` flag |

### Utilities (`src/utils/`, `src/lib/`)

| File | Description |
|---|---|
| `utils/constants.js` | App-wide constants: `ROOM_TYPES` (single/double/suite/family/villa), `TOUR_CATEGORIES` (adventure/cultural/beach/city/nature/food), `AMENITIES` (13 items), `BOOKING_STATUSES`, `CURRENCIES` (USD + VND with symbols), `DEFAULT_CURRENCY`, `ITEMS_PER_PAGE` (20) |
| `utils/formatters.js` | Formatting utilities: `formatCurrency` (Intl.NumberFormat), `formatDate` (date-fns format), `nightsBetween` (date diff), `truncate`, `slugify`, `starArray` |
| `utils/validators.js` | Validation functions: `isValidEmail`, `isStrongPassword` (≥8 chars), `isValidPhone`, `validateBookingDates` (past check, order check, max 30 nights) |
| `lib/utils.js` | `cn()` — merges Tailwind CSS classes using `clsx` + `tailwind-merge` |

### Router (`src/router/`)

| File | Description |
|---|---|
| `index.jsx` | `createBrowserRouter` config with two layout groups. **Public layout** (`AppLayout`): `/` (home, admin-redirected), `/login`, `/register`, `/hotels/search`, `/hotels/:id`, `/bookings/new` (protected, user-only), `/bookings/:id/confirmation`, `/tours`, `/tours/:id`, `/profile`, `/my-bookings`. **Admin layout** (`AdminLayout`): `/admin` (dashboard), `/admin/hotels`, `/admin/rooms`, `/admin/tours`, `/admin/bookings`, `/admin/users` — all admin-protected |

### Assets (`src/assets/`)

| File | Description |
|---|---|
| `hero.png` | Hero section background image |
| `react.svg` | React logo |
| `vite.svg` | Vite logo |

### Components — Common (`src/components/common/`)

| File | Description |
|---|---|
| `AppLayout.jsx` | Public site layout: sticky `Navbar` + `<main>` wrapped in `ErrorBoundary` and `PageTransition` + `Footer` + Sonner `Toaster` |
| `AdminLayout.jsx` | Admin panel layout: left sidebar (desktop) with navigation links (Dashboard, Hotels, Rooms, Tours, Bookings, Users) + user info + sign-out. Mobile: top bar + horizontal scrollable nav tabs. Content area with `ErrorBoundary` and `PageTransition` |
| `Navbar.jsx` | Responsive top navigation: brand logo, Hotels/Tours links, currency selector (USD/VND), user avatar dropdown (profile, bookings, wishlist, sign out) when authenticated, Sign In/Register buttons when not. Mobile hamburger menu |
| `Footer.jsx` | Site footer: brand, Company/Support/Explore link columns, copyright, Privacy Policy/Terms/Cookie Policy links |
| `ProtectedRoute.jsx` | Auth guard component: shows spinner during loading, redirects to `/login` if unauthenticated, to `/` if `requireAdmin` but not admin, to `/admin` if `userOnly` but is admin |
| `RedirectIfAdmin.jsx` | Redirect wrapper: if authenticated admin user, redirects to `/admin`. Otherwise renders children. Prevents admin from seeing customer-facing pages |
| `SearchBar.jsx` | Full-featured search bar with hotel/tour tab toggle, destination input with autocomplete suggestions (debounced API calls), date pickers (check-in/check-out), guest/room counter popup, search button. Supports `hero` and compact variants |
| `ErrorBoundary.jsx` | React class-based error boundary: catches render errors, shows friendly error UI with "Try Again" and "Go Home" buttons, exposes error details in dev mode |
| `Skeleton.jsx` | Loading placeholder components: base `Skeleton` (pulsing rounded div), `HotelCardSkeleton`, `TourCardSkeleton`, `DetailPageSkeleton`, `TableSkeleton`, `ProfileSkeleton` |
| `AnimatedCard.jsx` | Framer Motion wrapper: fade-in + slide-up on mount with staggered delay based on `index`, lifts on hover |
| `PageTransition.jsx` | Framer Motion page transition: fade + vertical slide on enter/exit |
| `Breadcrumb.jsx` | Breadcrumb navigation: renders linked items with chevron separators, last item is unlinked bold text |
| `EmptyState.jsx` | Empty state placeholder: animated scale-in, icon variants (search, empty, wishlist, reviews, bookings), title, description, optional action button link |
| `StarRating.jsx` | Star rating display: renders 5 stars, filled stars use warning color based on `rating` prop |
| `BookingStatusBadge.jsx` | Color-coded status badge: pending (yellow), confirmed (green), cancelled (red), completed (blue), paid (green), refunded (purple) |
| `PriceBreakdown.jsx` | Price breakdown panel: shows per-night × nights subtotal, 10% taxes, optional promo discount, bold total |

### Components — Hotel (`src/components/hotel/`)

| File | Description |
|---|---|
| `HotelCard.jsx` | Hotel list card: horizontal layout (image left, details right), star rating, property type badge, location, amenities tags (max 5 + overflow count), rating score badge with label (Exceptional/Excellent/etc.), price per night, "See Availability" CTA |
| `HotelFilters.jsx` | Sidebar filter panel: collapsible sections for price range (min/max inputs), star rating (checkboxes), review score (button group: Any/6+/7+/8+/9+), amenities (checkbox list, scrollable) |
| `ImageGallery.jsx` | Image gallery: 4-column grid (hero image spans 2 cols × 2 rows), remaining 4 thumbnails with "+N" overlay. Click opens fullscreen lightbox with prev/next navigation and image counter |

### Components — Review (`src/components/review/`)

| File | Description |
|---|---|
| `ReviewCard.jsx` | Review display: user avatar initial, name, date, rating badge, comment text |
| `ReviewForm.jsx` | Review submission form: interactive star rating with hover preview, comment textarea, submit button. Uses React Query mutation, shows toast on success/error, invalidates reviews cache |

### Components — Room (`src/components/room/`)

| File | Description |
|---|---|
| `RoomCard.jsx` | Room card: horizontal layout with image, room name, type badge, guest capacity, bed type, amenities tags, price per night, "Reserve" button |

### Components — Tour (`src/components/tour/`)

| File | Description |
|---|---|
| `TourCard.jsx` | Tour card: vertical layout with image (category badge overlay), name, location, duration, max participants, rating, price per person, "Book Now" CTA |

### Pages (`src/pages/`)

| File | Description |
|---|---|
| `HomePage.jsx` | Landing page: hero section with `SearchBar`, featured destinations grid, popular hotels (latest 4), trending tours (latest 4), value proposition section (Best Price, Free Cancellation, 24/7 Support, Secure Payment) |
| `LoginPage.jsx` | Login page: email/password form with show/hide toggle, error handling, redirects authenticated users (admin → `/admin`, user → previous page or `/`), link to register |
| `RegisterPage.jsx` | Registration page: user registration form (name, email, password, confirm password, terms checkbox) + collapsible admin registration section. Client-side validation (email, password strength, match). Auto-login after registration |
| `SearchResultsPage.jsx` | Hotel search results: compact search bar, sidebar filters (`HotelFilters`), sort dropdown, hotel cards with infinite scroll pagination, mobile filter drawer |
| `HotelDetailPage.jsx` | Hotel detail page: image gallery, breadcrumb, hotel info (stars, rating, location), description, amenity icons, rooms list (`RoomCard` with reserve action), reviews section with `ReviewForm` (if user has completed booking), booking sidebar |
| `BookingPage.jsx` | Booking checkout: booking summary (hotel, room, dates, guests), price breakdown with promo code application, guest info form, "Confirm & Pay" button. Creates booking via API, then creates Stripe payment, redirects to confirmation |
| `BookingConfirmationPage.jsx` | Booking confirmation: success animation, booking reference (copy to clipboard), booking details (dates, guests, price), PDF download (jsPDF), link to view all bookings |
| `ToursPage.jsx` | Tour listing: search input, category filter pills, sort dropdown, tour cards grid with infinite scroll, mobile filter panel |
| `TourDetailPage.jsx` | Tour detail page: image gallery, breadcrumb, tour info (location, duration, participants, category, rating), highlights, day-by-day itinerary (collapsible), includes/excludes lists, booking panel (date picker, participant counter, total price), reviews section |
| `ProfilePage.jsx` | User profile page with tab navigation: **Profile** tab (edit name, phone, avatar URL), **Bookings** tab (hotel + tour bookings list with status badges, cancel actions), **Wishlist** tab (saved hotels/tours), **Reviews** tab (user's reviews), **Settings** tab (change password) |
| `MyBookingsPage.jsx` | Redirect to `/profile?tab=bookings` |

### Pages — Admin (`src/pages/admin/`)

| File | Description |
|---|---|
| `AdminDashboard.jsx` | Admin dashboard: KPI cards (revenue, bookings, occupancy rate, new users), revenue line chart (Recharts), bookings by status pie chart, recent bookings table, quick-access links to management pages |
| `ManageHotels.jsx` | Hotel management: searchable table, create/edit modal (name, slug, city, country, star rating, base price, currency, property type, description), image upload, pagination, delete with confirmation |
| `ManageRooms.jsx` | Room management: searchable table, hotel selector, create/edit modal (name, room type, price, quantity, max guests, amenities, description), pagination, delete |
| `ManageTours.jsx` | Tour management: searchable table, create/edit modal (name, slug, city, country, category, duration, max participants, price, description), pagination, delete |
| `ManageBookings.jsx` | Booking management: searchable table with status filter tabs, inline status update dropdown, pagination |
| `ManageUsers.jsx` | User management: searchable table, inline role toggle (admin/user), active/inactive toggle, edit modal, delete with confirmation, pagination |

### Tests (`src/test/`)

| File | Description |
|---|---|
| `setup.js` | Vitest setup: imports `@testing-library/jest-dom`, mocks `window.scrollTo` and `window.matchMedia` |
| `formatters.test.js` | Tests for `formatCurrency`, `formatDate`, `nightsBetween`, `truncate`, `slugify` |
| `validators.test.js` | Tests for `isValidEmail`, `isStrongPassword`, `isValidPhone`, `validateBookingDates` |
| `HotelCard.test.jsx` | Component test for `HotelCard` rendering |
| `SearchBar.test.jsx` | Component test for `SearchBar` rendering |
| `TourCard.test.jsx` | Component test for `TourCard` rendering |

---

## Frontend Temp (`frontend-temp/`)

Temporary/scaffolding copy of the frontend, likely used during initial setup.

| File | Description |
|---|---|
| `.gitignore` | Same as frontend |
| `README.md` | Default Vite README |
| `eslint.config.js` | ESLint config |
| `index.html` | HTML entry point |
| `package.json` | Package config |
| `vite.config.js` | Vite config |
| `public/favicon.svg` | Favicon |
| `public/icons.svg` | Icon sprite |
| `src/App.css` | App styles |
| `src/App.jsx` | Default starter App component |
| `src/index.css` | Global styles |
| `src/main.jsx` | Entry point |
| `src/assets/hero.png` | Hero image |
| `src/assets/react.svg` | React logo |
| `src/assets/vite.svg` | Vite logo |
