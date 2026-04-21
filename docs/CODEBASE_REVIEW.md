# Travel Booking Website — Complete Codebase Review

> Last updated: **March 31, 2026**

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Models](#database-models)
- [Backend API Endpoints](#backend-api-endpoints)
  - [Authentication](#1-authentication-apiv1auth)
  - [Hotels](#2-hotels-apiv1hotels)
  - [Rooms](#3-rooms-apiv1rooms)
  - [Hotel Bookings](#4-hotel-bookings-apiv1bookings)
  - [Tours](#5-tours-apiv1tours)
  - [Tour Bookings](#6-tour-bookings-apiv1tour-bookings)
  - [Reviews](#7-reviews)
  - [Payments](#8-payments-apiv1payments)
  - [Wishlists](#9-wishlists-apiv1wishlists)
  - [Promo Codes](#10-promo-codes-apiv1promo-codes)
  - [Admin Panel](#11-admin-apiv1admin)
- [Backend Services (Business Logic)](#backend-services-business-logic)
- [Backend Middleware & Cross-Cutting](#backend-middleware--cross-cutting)
- [Frontend Pages & Components](#frontend-pages--components)
- [Frontend State Management](#frontend-state-management)
- [Frontend API Layer](#frontend-api-layer)
- [Utilities & Hooks](#utilities--hooks)
- [Design System & Styling](#design-system--styling)
- [Testing](#testing)
- [Infrastructure](#infrastructure)
- [Known Gaps & Issues](#known-gaps--issues)
- [Summary of All Features](#summary-of-all-features)

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Frontend   │────▶│   Backend    │────▶│ PostgreSQL  │
│  React/Vite  │     │  FastAPI     │     │  Database   │
│  Port: 5173  │     │  Port: 8000  │     │  Port: 5432 │
└─────────────┘     └──────┬───────┘     └────────────┘
                           │
                    ┌──────┴───────┐
                    │    Redis     │
                    │  Port: 6379  │
                    └──────────────┘
```

The project is a **full-stack travel booking website** that allows users to search and book hotels and tours. It includes an admin dashboard for managing all entities. The architecture is a **modular monolith** — one FastAPI backend, one React SPA frontend, shared PostgreSQL database, and Redis for token management.

---

## Tech Stack

| Layer            | Technology                                                                                      |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| **Frontend**     | React 19, Vite 8, TailwindCSS 4, Zustand 5, @tanstack/react-query 5, React Router v7           |
| **UI / Icons**   | lucide-react, framer-motion 12, recharts 3, sonner (toasts), react-helmet-async (SEO + OG tags) |
| **Maps**         | Leaflet + react-leaflet (interactive hotel/tour maps)                                           |
| **Stripe (FE)**  | @stripe/react-stripe-js + @stripe/stripe-js (installed, partially integrated)                   |
| **Date / PDF**   | date-fns (date utilities), jsPDF (booking confirmation PDF download)                            |
| **CSS Utilities**| clsx, tailwind-merge, class-variance-authority (installed but unused in source)                  |
| **Backend**      | Python 3.11, FastAPI 0.110, SQLAlchemy 2.0 (async), Alembic, Uvicorn                           |
| **Database**     | PostgreSQL 15 (via asyncpg)                                                                     |
| **Cache**        | Redis 7 (token blacklist)                                                                       |
| **Payments**     | Stripe (PaymentIntents + Webhooks)                                                              |
| **Storage**      | Cloudinary (image uploads)                                                                      |
| **Auth**         | JWT (access + refresh tokens), bcrypt password hashing, python-jose                              |
| **Email**        | aiosmtplib + Jinja2 in requirements (actual sending is a **logging placeholder**)               |
| **Rate Limit**   | slowapi (applied on auth endpoints)                                                             |
| **Testing (FE)** | Vitest 4 + @testing-library/react 16 + @testing-library/user-event + jest-dom (unit tests)     |
| **Testing (BE)** | pytest 8 + pytest-asyncio + httpx (async API integration tests) + aiosqlite (in-memory)        |
| **Infra**        | Docker Compose (postgres, redis, backend, frontend, pgadmin)                                    |

---

## Project Structure

```
Booking_Web_Project/
├── .env.example                 # Root env template (Postgres, Redis, JWT, Stripe, Cloudinary, SMTP)
├── .gitignore
├── docker-compose.yml           # 5 services: postgres, redis, backend, frontend, pgadmin
├── Instruction/
│   ├── CODEBASE_REVIEW.md       # This file
│   └── RUN_WEBSITE.md           # Setup & run instructions
├── backend/
│   ├── Dockerfile               # Python 3.11-slim, uvicorn --reload
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py               # Async Alembic config, imports all models
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       └── 002_add_hotel_currency.py
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan (Redis), routers, global error handler
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings: DB, Redis, JWT, Stripe, Cloudinary, email, frontend URL
│   │   │   ├── security.py      # Password hashing, JWT creation/decoding
│   │   │   └── dependencies.py  # get_current_user, require_admin, CurrentUser, AdminUser type aliases
│   │   ├── db/
│   │   │   ├── base.py          # Declarative Base: id (UUID), created_at, updated_at
│   │   │   └── session.py       # Async engine, session factory, get_db dependency
│   │   ├── models/              # SQLAlchemy ORM models (10 models)
│   │   ├── schemas/             # Pydantic request/response schemas (12 modules)
│   │   ├── api/v1/routes/       # HTTP route modules (11 routers)
│   │   └── services/            # Domain services (4 modules)
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_hotels.py
│       └── test_bookings.py
├── frontend/
│   ├── Dockerfile               # Node 20 Alpine, npm run dev --host
│   ├── package.json             # name: "frontend-tmp"
│   ├── vite.config.js           # React + Tailwind plugins, @ alias, /api proxy, Vitest config
│   ├── eslint.config.js         # Flat ESLint for JS/JSX
│   ├── index.html               # SPA entry shell
│   ├── .env.example             # VITE_API_BASE_URL, VITE_STRIPE_PUBLIC_KEY
│   ├── public/                  # favicon.svg, icons.svg
│   └── src/
│       ├── main.jsx             # App entry: QueryClient, HelmetProvider, auth initialize, RouterProvider
│       ├── App.jsx              # Dead code — default Vite counter (not imported anywhere)
│       ├── index.css            # Tailwind v4 import, @theme tokens, global styles
│       ├── router/index.jsx     # createBrowserRouter with all routes
│       ├── api/                 # Axios instance + 8 resource API modules
│       ├── components/
│       │   ├── common/          # 14 shared components (layout, nav, search, skeletons, etc.)
│       │   ├── hotel/           # HotelCard, HotelFilters, ImageGallery
│       │   ├── room/            # RoomCard
│       │   ├── tour/            # TourCard
│       │   └── review/          # ReviewCard, ReviewForm
│       ├── hooks/               # useAuth, useDebounce, useInfiniteScroll
│       ├── pages/               # 12 page components
│       │   └── admin/           # 6 admin page components
│       ├── store/               # 3 Zustand stores (auth, search, booking)
│       ├── utils/               # constants, validators, formatters
│       ├── lib/utils.js         # cn() class merging helper
│       ├── assets/              # Static images
│       └── test/                # Vitest setup + 5 test files
└── frontend-temp/               # Minimal Vite+React scaffold (NOT wired to docker-compose, unused)
```

---

## Database Models

Every model inherits from `Base` which provides:
- `id` — UUID primary key (auto-generated via `gen_random_uuid()`)
- `created_at` — timestamp with timezone (server default `now()`)
- `updated_at` — timestamp with timezone (auto-updates via `onupdate`)

### User

| Field             | Type         | Notes                              |
| ----------------- | ------------ | ---------------------------------- |
| `email`           | String(255)  | Unique, indexed                    |
| `hashed_password` | String(255)  | bcrypt hash (SHA-256 pre-hashed)   |
| `full_name`       | String(255)  |                                    |
| `phone`           | String(50)   | Optional                           |
| `avatar_url`      | Text         | Optional                           |
| `role`            | String(20)   | `"user"` or `"admin"` (enum)       |
| `is_active`       | Boolean      | Default `true`                     |
| `loyalty_points`  | Integer      | Default `0`, +1 per $1 spent       |

**Relationships:** bookings, tour_bookings, reviews, wishlists

### Hotel

| Field           | Type          | Notes                            |
| --------------- | ------------- | -------------------------------- |
| `name`          | String(255)   |                                  |
| `slug`          | String(255)   | Unique, indexed                  |
| `description`   | Text          | Optional                         |
| `address`       | String(500)   | Optional                         |
| `city`          | String(100)   | Indexed                          |
| `country`       | String(100)   | Indexed                          |
| `latitude`      | Float         | Optional                         |
| `longitude`     | Float         | Optional                         |
| `star_rating`   | Integer       | Default `3`                      |
| `property_type` | String(50)    | Optional (hotel/resort/apartment/villa/hostel) |
| `amenities`     | JSONB         | Array of amenity strings         |
| `images`        | JSONB         | Array of image URLs              |
| `base_price`    | Numeric(10,2) |                                  |
| `currency`      | String(10)    | Default `"USD"` (**added in migration 002**) |
| `avg_rating`    | Float         | Computed from reviews            |
| `total_reviews` | Integer       | Computed from reviews            |

**Relationships:** rooms (selectin, cascade delete-orphan), reviews (selectin)

### Room

| Field             | Type          | Notes                        |
| ----------------- | ------------- | ---------------------------- |
| `hotel_id`        | UUID (FK)     | References `hotels.id`       |
| `name`            | String(255)   |                              |
| `description`     | Text          | Optional                     |
| `room_type`       | String(50)    | single/double/suite/family/villa |
| `price_per_night` | Numeric(10,2) |                              |
| `total_quantity`  | Integer       | Default `1`                  |
| `max_guests`      | Integer       | Default `2`                  |
| `amenities`       | JSONB         | Array of amenity strings     |
| `images`          | JSONB         | Array of image URLs          |

**Relationships:** hotel, bookings

### Booking (Hotel Booking)

| Field              | Type          | Notes                              |
| ------------------ | ------------- | ---------------------------------- |
| `user_id`          | UUID (FK)     | References `users.id`              |
| `room_id`          | UUID (FK)     | References `rooms.id`              |
| `check_in`         | Date          | Indexed                            |
| `check_out`        | Date          | Indexed                            |
| `guests_count`     | Integer       | Default `1`                        |
| `total_price`      | Numeric(10,2) | Calculated: nights × price         |
| `status`           | String(20)    | `pending` → `confirmed` → `completed` / `cancelled` |
| `special_requests` | Text          | Optional                           |
| `promo_code_id`    | UUID (FK)     | Optional, references `promo_codes.id` |

**Relationships:** user, room, payment

### Tour

| Field              | Type          | Notes                            |
| ------------------ | ------------- | -------------------------------- |
| `name`             | String(255)   |                                  |
| `slug`             | String(255)   | Unique, indexed                  |
| `description`      | Text          | Optional                         |
| `city`             | String(100)   | Indexed                          |
| `country`          | String(100)   |                                  |
| `category`         | String(50)    | adventure/cultural/beach/city/nature/food |
| `duration_days`    | Integer       | Default `1`                      |
| `max_participants` | Integer       | Default `20`                     |
| `price_per_person` | Numeric(10,2) |                                  |
| `highlights`       | JSONB         | Array of highlight strings       |
| `itinerary`        | JSONB         | Array of day objects             |
| `includes`         | JSONB         | Array of included items          |
| `excludes`         | JSONB         | Array of excluded items          |
| `images`           | JSONB         | Array of image URLs              |
| `avg_rating`       | Float         | Computed from reviews            |
| `total_reviews`    | Integer       | Computed from reviews            |

**Relationships:** tour_bookings, reviews

### TourBooking

| Field               | Type          | Notes                              |
| ------------------- | ------------- | ---------------------------------- |
| `user_id`           | UUID (FK)     | References `users.id`              |
| `tour_id`           | UUID (FK)     | References `tours.id`              |
| `tour_date`         | Date          |                                    |
| `participants_count`| Integer       | Default `1`                        |
| `total_price`       | Numeric(10,2) | Calculated: participants × price   |
| `status`            | String(20)    | `pending` → `confirmed` → `completed` / `cancelled` |
| `special_requests`  | Text          | Optional                           |

**Relationships:** user, tour

### Payment

| Field                      | Type          | Notes                              |
| -------------------------- | ------------- | ---------------------------------- |
| `booking_id`               | UUID (FK)     | Optional, references `bookings.id` (ondelete SET NULL) |
| `stripe_payment_intent_id` | String(255)   | Unique, from Stripe                |
| `amount`                   | Numeric(10,2) |                                    |
| `currency`                 | String(10)    | Default `"usd"`                    |
| `status`                   | String(20)    | `pending` / `succeeded` / `failed` / `refunded` (enum) |

**Relationships:** booking

> **Note:** Payment model only has FK to `bookings` (hotel bookings). Tour booking payments are tracked via Stripe metadata only — no `tour_booking_id` FK exists on the Payment table.

### Review

| Field      | Type     | Notes                                      |
| ---------- | -------- | ------------------------------------------ |
| `user_id`  | UUID (FK)| References `users.id`                      |
| `hotel_id` | UUID (FK)| Optional — exactly one of hotel/tour       |
| `tour_id`  | UUID (FK)| Optional — exactly one of hotel/tour       |
| `rating`   | Integer  | 1-5 star rating                            |
| `comment`  | Text     | Optional                                   |

**Constraint:** Must have exactly one of `hotel_id` or `tour_id` (DB-level check).

**Relationships:** user, hotel, tour

### Wishlist

| Field      | Type     | Notes                                      |
| ---------- | -------- | ------------------------------------------ |
| `user_id`  | UUID (FK)| References `users.id`                      |
| `hotel_id` | UUID (FK)| Optional — exactly one of hotel/tour       |
| `tour_id`  | UUID (FK)| Optional — exactly one of hotel/tour       |

**Constraint:** Must have exactly one of `hotel_id` or `tour_id` (DB-level check).

**Relationships:** user, hotel (eager), tour (eager)

### PromoCode

| Field              | Type          | Notes                        |
| ------------------ | ------------- | ---------------------------- |
| `code`             | String(50)    | Unique, indexed              |
| `discount_percent` | Numeric(5,2)  | e.g. `10.00` = 10%          |
| `max_uses`         | Integer       | Default `100`                |
| `current_uses`     | Integer       | Default `0`, auto-increments |
| `min_booking_amount`| Numeric(10,2)| Default `0`                  |
| `is_active`        | Boolean       | Default `true`               |
| `expires_at`       | DateTime      | Optional expiration date     |

---

## Backend API Endpoints

### 1. Authentication (`/api/v1/auth`)

| Method | Endpoint              | Auth     | Rate Limit | Description                                   |
| ------ | --------------------- | -------- | ---------- | --------------------------------------------- |
| POST   | `/register`           | Public   | 5/min      | Create account, returns JWT access token       |
| POST   | `/login`              | Public   | 5/min      | Login with email/password, returns JWT         |
| POST   | `/logout`             | Optional | —          | Blacklists refresh token, clears cookie        |
| POST   | `/token/refresh`      | Cookie   | 10/min     | Rotate refresh token, get new access token     |
| POST   | `/password/forgot`    | Public   | 3/min      | Generates reset token, calls `_send_reset_email` (**currently a logging placeholder**) |
| POST   | `/password/reset`     | Public   | 5/min      | Reset password using token from email          |
| GET    | `/me`                 | User     | —          | Get current user profile                       |
| PATCH  | `/me`                 | User     | —          | Update current user profile (name, phone, etc) |

**Token flow:**
- Access token: JWT in `Authorization: Bearer <token>` header, expires in 15 minutes
- Refresh token: HTTP-only cookie (`refresh_token`), expires in 7 days, path scoped to `/api/v1/auth`, `SameSite=strict`, `Secure=false` (dev)
- Refresh token rotation: old token blacklisted on refresh, new pair issued
- Refresh token blacklisting via Redis (`blacklist:{jti}` with TTL) to prevent reuse
- Password hashing: SHA-256 pre-hash → bcrypt

**Password reset flow:**
1. User provides email → backend generates 1-hour JWT with `type: "password_reset"`
2. `_send_reset_email()` is called as a background task — **currently only logs** the reset link (placeholder)
3. Frontend URL constructed as `{FRONTEND_URL}/reset-password?token={token}`
4. User submits new password + token → token verified → password updated

### 2. Hotels (`/api/v1/hotels`)

| Method | Endpoint              | Auth          | Description                                            |
| ------ | --------------------- | ------------- | ------------------------------------------------------ |
| GET    | `/`                   | Public        | List hotels with filtering, sorting, pagination         |
| GET    | `/{hotel_id}`         | Public        | Get single hotel details                                |
| POST   | `/`                   | Authenticated | Create a new hotel                                      |
| PUT    | `/{hotel_id}`         | Authenticated | Full replace of hotel data                              |
| PATCH  | `/{hotel_id}`         | Authenticated | Partial update of hotel data                            |
| DELETE | `/{hotel_id}`         | Authenticated | Delete a hotel (cascades to rooms)                      |
| POST   | `/{hotel_id}/images`  | Authenticated | Upload images to Cloudinary, append URLs to hotel       |

**List filters:** `city`, `country`, `check_in`/`check_out` (availability), `guests`, `min_price`, `max_price`, `star_rating`, `amenities` (comma-separated), `property_type`, `search` (text search on name/description via `ILIKE`)

**Sorting:** `created_at`, `base_price`, `avg_rating`, `star_rating`, `name` (asc/desc)

**Availability logic:** When `check_in` and `check_out` provided, filters to hotels that have at least one room not fully booked (status `pending`/`confirmed`) during the requested date range. Optionally filters by `max_guests >= guests`.

### 3. Rooms (`/api/v1/rooms`)

| Method | Endpoint                            | Auth          | Description                               |
| ------ | ----------------------------------- | ------------- | ----------------------------------------- |
| GET    | `/hotels/{hotel_id}/rooms`          | Public        | List rooms for a hotel (with availability) |
| POST   | `/hotels/{hotel_id}/rooms`          | Authenticated | Create a room for a hotel                  |
| GET    | `/rooms/{room_id}`                  | Public        | Get single room details                    |
| PUT    | `/rooms/{room_id}`                  | Authenticated | Full replace of room data                  |
| PATCH  | `/rooms/{room_id}`                  | Authenticated | Partial update of room data                |
| DELETE | `/rooms/{room_id}`                  | Authenticated | Delete a room                              |
| GET    | `/rooms/{room_id}/availability`     | Public        | Check if room is available for dates       |
| POST   | `/rooms/{room_id}/images`           | Authenticated | Upload images to Cloudinary for room       |

**Availability check:** Returns `{ available: bool, rooms_left: int }` by counting overlapping bookings vs `total_quantity`.

### 4. Hotel Bookings (`/api/v1/bookings`)

| Method | Endpoint          | Auth | Description                                            |
| ------ | ----------------- | ---- | ------------------------------------------------------ |
| POST   | `/`               | User | Create a hotel booking (with availability check)        |
| GET    | `/`               | User | List current user's hotel bookings (filterable by status)|
| GET    | `/{booking_id}`   | User | Get booking details (includes room info)                |
| PATCH  | `/{booking_id}`   | User | Update booking (only if pending/confirmed)              |
| DELETE | `/{booking_id}`   | User | Cancel a booking (sets status to `cancelled`)           |

**Booking creation flow (availability_service.check_and_reserve):**
1. Validates `check_out > check_in`
2. Acquires `SELECT ... FOR UPDATE` lock on the Room row (prevents double-booking)
3. Checks `guests_count <= room.max_guests`
4. Counts overlapping bookings (pending/confirmed) — must be < `room.total_quantity`
5. Calculates `total_price = price_per_night × nights`
6. If `promo_code` provided: validates and applies discount (percent off)
7. Creates `Booking` with status `pending`

### 5. Tours (`/api/v1/tours`)

| Method | Endpoint             | Auth          | Description                                  |
| ------ | -------------------- | ------------- | -------------------------------------------- |
| GET    | `/`                  | Public        | List tours with filtering, sorting, pagination|
| GET    | `/{tour_id}`         | Public        | Get single tour details                       |
| POST   | `/`                  | Authenticated | Create a new tour                             |
| PUT    | `/{tour_id}`         | Authenticated | Full replace of tour data                     |
| PATCH  | `/{tour_id}`         | Authenticated | Partial update of tour data                   |
| DELETE | `/{tour_id}`         | Authenticated | Delete a tour                                 |
| POST   | `/{tour_id}/images`  | Authenticated | Upload images to Cloudinary for tour          |

**List filters:** `city`, `country`, `category`, `q` (text search), `min_price`, `max_price`, `duration`

**Sorting:** `created_at`, `price_per_person`, `avg_rating`, `duration_days`, `name` (asc/desc)

### 6. Tour Bookings (`/api/v1/tour-bookings`)

| Method | Endpoint          | Auth | Description                                     |
| ------ | ----------------- | ---- | ----------------------------------------------- |
| POST   | `/`               | User | Book a tour for a specific date                  |
| GET    | `/`               | User | List current user's tour bookings                |
| GET    | `/{booking_id}`   | User | Get tour booking details                         |
| PATCH  | `/{booking_id}`   | User | Update tour booking (participants, requests)     |
| DELETE | `/{booking_id}`   | User | Cancel tour booking                              |

**Tour booking creation flow:**
1. Acquires `SELECT ... FOR UPDATE` lock on Tour row
2. Sums existing participants for the same `tour_id` + `tour_date` (pending/confirmed)
3. Checks if `existing + requested <= max_participants`
4. Calculates `total_price = price_per_person × participants_count`
5. Creates `TourBooking` with status `pending`

### 7. Reviews

| Method | Endpoint                       | Auth | Description                                |
| ------ | ------------------------------ | ---- | ------------------------------------------ |
| GET    | `/hotels/{hotel_id}/reviews`   | Public| List reviews for a hotel (sorted, paginated)|
| GET    | `/tours/{tour_id}/reviews`     | Public| List reviews for a tour (sorted, paginated) |
| POST   | `/reviews`                     | User | Create a review for a hotel OR tour         |
| PATCH  | `/reviews/{review_id}`         | User | Update own review                           |
| DELETE | `/reviews/{review_id}`         | User/Admin | Delete review (owner or admin — **only explicit admin check in the codebase**) |

**Review creation rules:**
- Must provide exactly one of `hotel_id` or `tour_id`
- **Hotel review:** User must have a `completed` booking at that hotel
- **Tour review:** User must have a `completed` tour booking for that tour
- One review per user per hotel/tour (enforced at API level)
- After create/update/delete: recalculates `avg_rating` and `total_reviews` on the parent entity

### 8. Payments (`/api/v1/payments`)

| Method | Endpoint          | Auth  | Description                                    |
| ------ | ----------------- | ----- | ---------------------------------------------- |
| POST   | `/`               | User  | Create a Stripe PaymentIntent for a booking     |
| GET    | `/{payment_id}`   | User  | Get payment status                              |
| POST   | `/webhooks`       | Stripe| Handle Stripe webhook events (signature verified)|
| DELETE | `/{payment_id}`   | Admin | Issue a full refund via Stripe                  |

**Payment flow:**
1. `create_payment_intent`: Creates Stripe PaymentIntent, stores local `Payment` record, returns `client_secret`
2. Frontend uses `client_secret` to complete payment via Stripe.js
3. Stripe sends webhook → `handle_webhook_event`:
   - `payment_intent.succeeded` → updates Payment status, sets Booking to `confirmed`, awards loyalty points
   - `payment_intent.payment_failed` → updates Payment status to `failed`
4. Refund: Calls `stripe.Refund.create()`, sets Payment to `refunded`, Booking to `cancelled`

**Loyalty points:** 1 point per $1 spent (awarded on successful payment)

**Service-level support:** `create_payment_intent` accepts both `booking_id` and `tour_booking_id` parameters, but the `Payment` DB model only has FK to `bookings` — tour booking payments are tracked via Stripe metadata only.

### 9. Wishlists (`/api/v1/wishlists`)

| Method | Endpoint            | Auth | Description                           |
| ------ | ------------------- | ---- | ------------------------------------- |
| GET    | `/`                 | User | List current user's wishlisted items   |
| POST   | `/`                 | User | Add a hotel or tour to wishlist        |
| DELETE | `/{wishlist_id}`    | User | Remove item from wishlist              |

**Rules:** Must provide exactly one of `hotel_id` or `tour_id`. Duplicate entries are rejected (409 Conflict).

### 10. Promo Codes (`/api/v1/promo-codes`)

| Method | Endpoint          | Auth          | Description                                   |
| ------ | ----------------- | ------------- | --------------------------------------------- |
| POST   | `/validate`       | User          | Validate a promo code against a booking amount |
| POST   | `/`               | Authenticated | Create a new promo code                        |
| GET    | `/`               | Authenticated | List all promo codes (paginated)               |
| PATCH  | `/{promo_id}`     | Authenticated | Update a promo code                            |
| DELETE | `/{promo_id}`     | Authenticated | Delete a promo code                            |

**Validation checks:** Code exists, is active, not expired, not at max uses, booking amount >= minimum.

### 11. Admin (`/api/v1/admin`)

| Method | Endpoint               | Auth          | Description                                    |
| ------ | ---------------------- | ------------- | ---------------------------------------------- |
| GET    | `/stats`               | Authenticated | Dashboard statistics (revenue, bookings, users) |
| GET    | `/users`               | Authenticated | List all users (searchable by name/email, paginated) |
| GET    | `/users/{user_id}`     | Authenticated | Get user details                                |
| PATCH  | `/users/{user_id}`     | Authenticated | Update user (role, active status, etc.)         |
| DELETE | `/users/{user_id}`     | Authenticated | Delete a user                                   |
| GET    | `/bookings`            | Authenticated | List all hotel bookings (filterable by status, paginated) |
| PATCH  | `/bookings/{booking_id}` | Authenticated | Update booking status (via query param `status`) |

> **⚠ Authorization gap:** All admin routes use `CurrentUser` (any authenticated user) instead of `AdminUser` (admin role check). See [Known Gaps](#known-gaps--issues).

**Dashboard stats (by period: week/month/year):**
- `total_revenue` — sum of succeeded payments
- `bookings_count` — total hotel bookings created
- `new_users` — newly registered users
- `occupancy_rate` — booked rooms (confirmed/completed) / total room quantity (%)
- `revenue_chart_data` — daily revenue breakdown (date + revenue pairs)
- `bookings_by_status` — count per status (pending, confirmed, etc.)
- `recent_bookings` — last 10 bookings (id, user_id, room_id, check_in, check_out, total_price, status, created_at)

---

## Backend Services (Business Logic)

### auth_service.py
| Function                     | Description                                              |
| ---------------------------- | -------------------------------------------------------- |
| `register_user(db, data)`    | Checks email uniqueness, hashes password, creates User   |
| `authenticate_user(db, email, password)` | Verifies credentials, checks account active   |
| `issue_tokens(user_id, role)` | Creates access + refresh JWT pair                       |
| `blacklist_token(redis, jti)` | Adds token JTI to Redis blacklist with TTL (`blacklist:{jti}`) |
| `is_token_blacklisted(redis, jti)` | Checks if token JTI is blacklisted              |
| `validate_refresh_token(redis, token)` | Decodes token, checks type=refresh & blacklist |
| `create_password_reset_token(user_id)` | Creates 1-hour JWT with type=password_reset   |
| `verify_password_reset_token(token)` | Validates reset token, returns user_id         |
| `reset_user_password(db, user_id, new_password)` | Updates user's hashed password     |

### security.py
| Function                      | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `hash_password(password)`     | SHA-256 pre-hash → bcrypt hash                          |
| `verify_password(plain, hashed)` | Verifies password against bcrypt hash                |
| `create_access_token(subject, extra)` | Creates JWT access token (15 min expiry, type=access) |
| `create_refresh_token(subject)` | Creates JWT refresh token (7 day expiry, type=refresh) with JTI |
| `decode_token(token)`         | Decodes and validates JWT, raises ValueError on failure |

### availability_service.py
| Function                      | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `check_and_reserve(db, ...)`  | Atomically checks room availability and creates booking with row-level locking (`SELECT ... FOR UPDATE`) |
| `_promo_is_valid(promo, amount)` | Validates promo code (expiry, uses, min amount)      |

### payment_service.py
| Function                          | Description                                         |
| --------------------------------- | --------------------------------------------------- |
| `create_payment_intent(db, ...)`  | Creates Stripe PaymentIntent, stores local Payment record; accepts both `booking_id` and `tour_booking_id` |
| `handle_webhook_event(db, event)` | Processes Stripe webhooks — `succeeded` → confirm booking + loyalty points; `failed` → update status |
| `refund_payment(db, payment_id)`  | Issues Stripe refund, cancels booking, sets payment to refunded |
| `_award_loyalty_points(db, user_id, amount)` | Awards 1 point per $1 to user          |

### cloudinary_service.py
| Function                        | Description                                           |
| ------------------------------- | ----------------------------------------------------- |
| `upload_image(file, folder)`    | Uploads single image to Cloudinary, returns URL        |
| `upload_images(files, folder)`  | Uploads multiple images, returns list of URLs          |

### dependencies.py
| Function              | Description                                                 |
| --------------------- | ----------------------------------------------------------- |
| `get_current_user(db, ...)` | Extracts user from Bearer header or `access_token` cookie, validates JWT, checks active status |
| `require_admin(current_user)` | Ensures user has `admin` role (returns 403 if not) — **defined but not used in any route** |
| `CurrentUser`         | Type alias for dependency-injected authenticated user       |
| `AdminUser`           | Type alias for dependency-injected admin user — **defined but not used in any route** |

---

## Backend Middleware & Cross-Cutting

### Middleware (registered in `main.py`)
| Middleware | Configuration |
| ---------- | ------------- |
| **CORSMiddleware** | Origins: `[settings.FRONTEND_URL]`, credentials: true, all methods/headers |
| **Rate Limit Handler** | `slowapi.RateLimitExceeded` → `_rate_limit_exceeded_handler` |

### Global Exception Handler
- Catches all unhandled `Exception` → returns HTTP 500 with `{"success": false, "message": "Internal server error", "detail": str(exc)}`

### Redis Lifespan
- Redis connection opened in `lifespan()`, stored as `app.state.redis`, closed on shutdown

### Rate Limiting
- `Limiter` from slowapi is instantiated per-module (e.g., in `auth.py`) using `get_remote_address` as key function
- Applied with `@limiter.limit()` decorator on auth endpoints: register (5/min), login (5/min), refresh (10/min), forgot password (3/min), reset password (5/min)
- **Note:** `app.state.limiter` is not explicitly set in `main.py` — slowapi may require this for full functionality

---

## Frontend Pages & Components

### Pages

| Page                     | Route                       | Auth     | Description                                          |
| ------------------------ | --------------------------- | -------- | ---------------------------------------------------- |
| `HomePage`               | `/`                         | Public   | Hero search bar, featured destinations (6 cities), popular hotels (top 4 by rating), top tours (top 4 by rating), value propositions (4 cards), OG meta tags |
| `LoginPage`              | `/login`                    | Public   | Email/password login form with Helmet title           |
| `RegisterPage`           | `/register`                 | Public   | Registration form (name, email, password, phone) with validation |
| `SearchResultsPage`      | `/hotels/search`            | Public   | Hotel search with filters (price, stars, amenities), sorting, infinite scroll via IntersectionObserver |
| `HotelDetailPage`        | `/hotels/:id`               | Public   | Hotel info, image gallery, amenities, available rooms, reviews, reserve button, interactive map (Leaflet) |
| `BookingPage`            | `/bookings/new`             | User     | Guest details form, date selection, promo code input (validates via adminApi), price breakdown, booking creation |
| `BookingConfirmationPage`| `/bookings/:id/confirmation`| User     | Success screen with animated checkmark (framer-motion), booking reference, details, PDF download (jsPDF), copy reference button |
| `ToursPage`              | `/tours`                    | Public   | Tour listing with category filter, search, price filter, sorting, infinite scroll |
| `TourDetailPage`         | `/tours/:id`                | Public   | Tour info, image gallery, highlights, itinerary, includes/excludes, reviews, booking panel, interactive map (Leaflet) |
| `ProfilePage`            | `/profile`                  | User     | Tabbed profile page (6 tabs — see below), query param driven (`?tab=`) |
| `MyBookingsPage`         | `/my-bookings`              | User     | Redirects to `/profile?tab=bookings`                 |
| `AdminDashboard`         | `/admin`                    | User*    | Stats dashboard (revenue, bookings, occupancy, charts via Recharts) |
| `ManageHotels`           | `/admin/hotels`             | User*    | CRUD table for hotels with search, pagination, modal form (create/edit), image management (upload, reorder, set thumbnail) |
| `ManageRooms`            | `/admin/rooms`              | User*    | CRUD table for rooms                                 |
| `ManageTours`            | `/admin/tours`              | User*    | CRUD table for tours                                 |
| `ManageBookings`         | `/admin/bookings`           | User*    | View/update booking statuses                         |
| `ManageUsers`            | `/admin/users`              | User*    | View/update/delete users                             |

> **\*Admin pages:** `ProtectedRoute` wraps admin routes but **never passes** `requireAdmin={true}`, so any authenticated user can access them. The Navbar also shows the Dashboard link to all authenticated users without role check.

### ProfilePage Tabs

| Tab        | Description                                                        |
| ---------- | ------------------------------------------------------------------ |
| Profile    | Edit name, email, phone; avatar display with camera button; member since date |
| Bookings   | Sub-tabs for hotel bookings and tour bookings; cancel pending ones; displays room/tour name, dates, guests, price, status badge |
| Reviews    | List all user's reviews (hotel + tour combined, sorted by date); delete option |
| Wishlist   | Grid of wishlisted hotels/tours with name, city; remove option     |
| Loyalty    | Points display, tier progress bar (Bronze 0 / Silver 500 / Gold 1500 / Platinum 5000), earning rules info |
| Security   | Change password form (current password, new password, confirm new password) with client-side validation |

### Reusable Components

| Component           | Location                        | Description                                       |
| ------------------- | ------------------------------- | ------------------------------------------------- |
| `AppLayout`         | `components/common/`            | Main layout: Navbar + ErrorBoundary + PageTransition + Outlet + Footer + Sonner Toaster (top-right, rich colors, close button) |
| `Navbar`            | `components/common/`            | Sticky top nav, responsive (desktop dropdown + mobile hamburger), auth-aware user menu, currency picker (local state, not persisted), Dashboard link for all auth'd users |
| `Footer`            | `components/common/`            | Site footer                                        |
| `SearchBar`         | `components/common/`            | Destination/date/guest search bar with two variants (hero & compact), debounced hotel suggestions dropdown (React Query + useDebounce), hotels/tours tab switcher, guest counter (adults/children/rooms) |
| `ProtectedRoute`    | `components/common/`            | Auth guard with loading spinner, optional `requireAdmin` prop (supports it but **never used with true**) |
| `Breadcrumb`        | `components/common/`            | Navigation breadcrumbs                             |
| `PriceBreakdown`    | `components/common/`            | Price calculation display (nights × rate - discount)|
| `BookingStatusBadge`| `components/common/`            | Colored status badge (pending/confirmed/etc.)      |
| `StarRating`        | `components/common/`            | Star rating display                                |
| `Skeleton`          | `components/common/`            | Loading skeleton components + `HotelCardSkeleton` + `TourCardSkeleton` exports |
| `AnimatedCard`      | `components/common/`            | Framer Motion card wrapper with entrance animation |
| `EmptyState`        | `components/common/`            | Empty content placeholder with motion              |
| `ErrorBoundary`     | `components/common/`            | React error boundary                               |
| `PageTransition`    | `components/common/`            | Framer Motion page transition animation wrapper    |
| `HotelCard`         | `components/hotel/`             | Hotel listing card (image, price, rating, location)|
| `HotelFilters`      | `components/hotel/`             | Sidebar filter panel for hotel search              |
| `ImageGallery`      | `components/hotel/`             | Image gallery/carousel                             |
| `TourCard`          | `components/tour/`              | Tour listing card (image, price, duration, rating) |
| `RoomCard`          | `components/room/`              | Room card with details and reserve button          |
| `ReviewCard`        | `components/review/`            | Single review display (user, rating, comment)      |
| `ReviewForm`        | `components/review/`            | Form to submit a review (star rating + comment textarea, useMutation to reviews API) |

---

## Frontend State Management

### Zustand Stores

#### `authStore` (global auth state)
| State/Action       | Description                                                   |
| ------------------ | ------------------------------------------------------------- |
| `user`             | Current user object (or null)                                 |
| `accessToken`      | JWT access token string                                       |
| `isAuthenticated`  | Boolean auth status                                           |
| `isLoading`        | True during initialization                                    |
| `login(email, pw)` | Calls login API, stores token, fetches user profile           |
| `register(data)`   | Calls register API, stores token, fetches user profile        |
| `logout()`         | Calls logout API, clears state                                |
| `refreshToken()`   | Refreshes access token via cookie-based refresh               |
| `updateProfile(data)` | Updates user profile via API                               |
| `initialize()`     | Called on app load (before render) — attempts to refresh token |

#### `bookingStore` (booking flow state)
| State/Action       | Description                                                   |
| ------------------ | ------------------------------------------------------------- |
| `selectedRoom`     | Room object selected for booking                              |
| `hotel`            | Hotel object for the selected room                            |
| `checkIn/checkOut` | Selected dates                                                |
| `guests`           | Guest count (default 1)                                       |
| `promoCode`        | Applied promo code string                                     |
| `discount`         | Calculated discount amount                                    |
| `setBookingData()` | Sets any booking data fields                                  |
| `applyPromo()`     | Sets promo code and discount                                  |
| `clearBooking()`   | Resets all booking state                                      |

#### `searchStore` (search bar state)
| State/Action        | Description                                                  |
| ------------------- | ------------------------------------------------------------ |
| `destination`       | Search destination text                                      |
| `checkIn/checkOut`  | Selected date range                                          |
| `guests`            | Object: `{ adults, children, rooms }`                        |
| `searchType`        | `"hotels"` or `"tours"`                                      |
| `setDestination()`  | Updates destination                                          |
| `setDates()`        | Updates date range                                           |
| `setGuests()`       | Updates guest counts                                         |
| `setSearchType()`   | Switches between hotels/tours                                |
| `resetSearch()`     | Clears all search state                                      |

### TanStack React Query
- `QueryClient` configured in `main.jsx`: staleTime 5 minutes, 1 retry, no refetch on window focus
- Used throughout pages and components for server state: `useQuery`, `useMutation`, `useQueryClient`
- Query key patterns: `['popular-hotels']`, `['top-tours']`, `['hotel', id]`, `['booking', id]`, `['admin-hotels', page, search]`, `['my-bookings']`, `['my-tour-bookings']`, `['my-wishlists']`, `['my-hotel-reviews']`, `['my-tour-reviews']`, `['hotel-search-suggestions', debouncedDest]`

---

## Frontend API Layer

All API calls go through `axiosInstance.js` which:
1. Sets base URL to `VITE_API_BASE_URL` (or `/api/v1`)
2. Sends `withCredentials: true` (for refresh cookie)
3. Attaches `Authorization: Bearer <token>` from auth store (request interceptor)
4. **Auto-refreshes**: On 401 response, attempts token refresh and retries request
5. Queues concurrent requests during refresh to avoid multiple refresh calls

### API Modules

| Module          | Functions                                                            |
| --------------- | -------------------------------------------------------------------- |
| `authApi`       | `register`, `login`, `logout`, `refreshToken`, `forgotPassword`, `resetPassword`, `getMe`, `updateMe`, `changePassword` |
| `hotelsApi`     | `list`, `get`, `create`, `update`, `replace`, `delete`, `uploadImages` |
| `roomsApi`      | `listByHotel`, `get`, `create`, `update`, `delete`, `checkAvailability` |
| `bookingsApi`   | `list`, `get`, `create`, `update`, `cancel`                          |
| `toursApi`      | `list`, `get`, `create`, `update`, `delete`, `listBookings`, `getBooking`, `createBooking`, `updateBooking`, `cancelBooking` |
| `paymentsApi`   | `create`, `get`, `refund` (imported in BookingPage but not actively called) |
| `reviewsApi`    | `listHotelReviews`, `listTourReviews`, `create`, `update`, `delete`  |
| `adminApi`      | `getStats`, `listUsers`, `getUser`, `updateUser`, `deleteUser`, `listBookings`, `updateBooking`, `listPromoCodes`, `createPromoCode`, `updatePromoCode`, `deletePromoCode`, `validatePromoCode`, `listWishlists`, `addToWishlist`, `removeFromWishlist` |

### Vite Dev Proxy
- `/api` → `http://localhost:8000` (configured in `vite.config.js`)

---

## Utilities & Hooks

### Utility Functions (`utils/` and `lib/`)

| Function              | File            | Description                                    |
| --------------------- | --------------- | ---------------------------------------------- |
| `formatCurrency()`    | `formatters.js` | Formats number as currency (e.g. `$1,234.56`)  |
| `formatDate()`        | `formatters.js` | Formats date string to `MMM dd, yyyy`          |
| `nightsBetween()`     | `formatters.js` | Calculates nights between two dates            |
| `truncate()`          | `formatters.js` | Truncates string with `...`                    |
| `slugify()`           | `formatters.js` | Converts text to URL-safe slug                 |
| `starArray()`         | `formatters.js` | Returns boolean array for star rating display  |
| `isValidEmail()`      | `validators.js` | Email format validation                        |
| `isStrongPassword()`  | `validators.js` | Password strength check (min 8 chars)          |
| `isValidPhone()`      | `validators.js` | Phone number format validation                 |
| `validateBookingDates()` | `validators.js` | Validates check-in/out (not past, max 30 nights) |
| `cn(...inputs)`       | `lib/utils.js`  | Merges Tailwind classes with `clsx` + `tailwind-merge` |

### Constants (`utils/constants.js`)

| Constant          | Value                                                                    |
| ----------------- | ------------------------------------------------------------------------ |
| `ROOM_TYPES`      | `['single', 'double', 'suite', 'family', 'villa']`                      |
| `TOUR_CATEGORIES` | `['adventure', 'cultural', 'beach', 'city', 'nature', 'food']`          |
| `AMENITIES`       | 13 amenities: wifi, pool, gym, spa, parking, restaurant, bar, room_service, air_conditioning, laundry, airport_shuttle, pet_friendly, business_center |
| `BOOKING_STATUSES`| `['pending', 'confirmed', 'cancelled', 'completed']`                     |
| `CURRENCIES`      | `[{ code: 'USD', symbol: '$', name: 'US Dollar' }, { code: 'VND', symbol: '₫', name: 'Vietnamese Dong' }]` |
| `DEFAULT_CURRENCY`| `'USD'`                                                                  |
| `ITEMS_PER_PAGE`  | `20`                                                                     |

### Custom Hooks (`hooks/`)

| Hook               | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `useAuth()`        | Convenience wrapper around `authStore` — returns `user`, `isAuthenticated`, `isAdmin` (`user?.role === 'admin'`), `login`, `logout`, `register`, `refreshToken`, `updateProfile` |
| `useDebounce(value, delay)` | Debounces a value by `delay` ms (default 300ms) — used in SearchBar |
| `useInfiniteScroll(callback, options)` | IntersectionObserver-based infinite scroll trigger — used in SearchResultsPage and ToursPage |

---

## Design System & Styling

### Approach
- **Tailwind CSS v4** via `@tailwindcss/vite` plugin (no `tailwind.config.js` — uses CSS-based `@theme`)
- **Global styles** in `src/index.css`
- **Class merging:** `cn()` helper using `clsx` + `tailwind-merge` in `lib/utils.js`
- **No CSS modules or styled-components**
- **Form handling:** All controlled components with `useState` — no form library (React Hook Form, Formik, etc.)

### Design Tokens (`@theme` in `index.css`)

| Token                | Value                                    |
| -------------------- | ---------------------------------------- |
| `--color-primary`    | `#003580` (dark blue)                    |
| `--color-primary-light` | `#0055a0`                             |
| `--color-primary-dark`  | `#002050`                             |
| `--color-accent`     | `#FF6B35` (orange)                       |
| `--color-accent-light`  | `#FF8A5C`                             |
| `--color-accent-dark`   | `#E05520`                             |
| `--color-success`    | `#10B981` (green)                        |
| `--color-warning`    | `#F59E0B` (amber)                        |
| `--color-error`      | `#EF4444` (red)                          |
| `--color-surface`    | `#F8FAFC` (light gray)                   |
| `--color-muted`      | `#64748B` (slate gray)                   |
| `--font-heading`     | `'Plus Jakarta Sans', sans-serif`        |
| `--font-body`        | `'Inter', sans-serif`                    |
| `--radius-card`      | `8px`                                    |
| `--radius-input`     | `4px`                                    |
| `--radius-pill`      | `50px`                                   |

### Global CSS Features
- Google Fonts loaded via `@import url()`
- `:focus-visible` outline: 2px solid primary with 2px offset (accessibility)
- `.sr-only` class for screen-reader-only content
- Box-sizing border-box reset

---

## Testing

### Backend (`backend/tests/`)

| File                 | Coverage                                                       |
| -------------------- | -------------------------------------------------------------- |
| `conftest.py`        | Async test client, DB session (aiosqlite in-memory), user/admin fixtures |
| `test_auth.py`       | Register, login, token refresh, logout, password reset         |
| `test_hotels.py`     | Hotel CRUD, image upload, availability filtering               |
| `test_bookings.py`   | Booking creation (availability, double-book prevention), cancel |

**Stack:** `pytest 8` + `pytest-asyncio` + `httpx` (async test client) + `aiosqlite` (in-memory SQLite for tests)

### Frontend (`frontend/src/test/`)

| File                     | Coverage                                          |
| ------------------------ | ------------------------------------------------- |
| `formatters.test.js`     | `formatCurrency`, `formatDate`, `nightsBetween`, etc. |
| `validators.test.js`     | `isValidEmail`, `isStrongPassword`, `isValidPhone`, `validateBookingDates` |
| `HotelCard.test.jsx`     | Renders hotel name, price, rating; click events   |
| `TourCard.test.jsx`      | Renders tour name, duration, price, category badge|
| `SearchBar.test.jsx`     | Destination input, date pickers, guest selector, search submit |

**Stack:** `Vitest 4` + `@testing-library/react 16` + `@testing-library/jest-dom` + `@testing-library/user-event` + `jsdom`

**Setup (`test/setup.js`):** Imports jest-dom matchers, stubs `window.scrollTo` and `window.matchMedia` for jsdom compatibility.

**Scripts:**
- `npm run test` — single run (`vitest run`)
- `npm run test:watch` — watch mode (`vitest`)

---

## Infrastructure

### Docker Compose Services

| Service      | Image              | Port      | Purpose                           | Health Check           |
| ------------ | ------------------ | --------- | --------------------------------- | ---------------------- |
| `postgres`   | postgres:15-alpine | `${POSTGRES_PORT}:5432` | Primary database    | `pg_isready`           |
| `redis`      | redis:7-alpine     | `${REDIS_PORT}:6379`    | Token blacklist cache | `redis-cli ping`      |
| `backend`    | Custom Dockerfile  | `8000:8000` | FastAPI application             | —                      |
| `frontend`   | Custom Dockerfile  | `5173:5173` | Vite React dev server           | —                      |
| `pgadmin`    | dpage/pgadmin4     | `${PGADMIN_PORT}:80` | Database admin UI (admin@travel.com / admin) | — |

**Networks:** `travel_network` (bridge)
**Volumes:** `postgres_data`, `redis_data` (persistent)
**Dependency chain:** postgres + redis (healthy) → backend → frontend

### Health Check

| Method | Endpoint  | Auth   | Description                 |
| ------ | --------- | ------ | --------------------------- |
| GET    | `/health` | Public | Returns `{ "status": "ok" }` |

### Environment Variables

#### Root `.env.example` (used by Docker Compose & backend)

| Group         | Variables                                                              |
| ------------- | ---------------------------------------------------------------------- |
| Infrastructure | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `DATABASE_URL`, `REDIS_PORT`, `REDIS_URL`, `PGADMIN_PORT` |
| Auth / JWT    | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` |
| Stripe        | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Cloudinary    | `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` |
| SMTP / Email  | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `FROM_EMAIL`  |
| Frontend      | `FRONTEND_URL`                                                         |

#### Frontend `.env.example`

| Variable              | Default                              |
| --------------------- | ------------------------------------ |
| `VITE_API_BASE_URL`   | `http://localhost:8000/api/v1`       |
| `VITE_STRIPE_PUBLIC_KEY` | (Stripe test publishable key)     |

### Database Migrations (Alembic)

| Revision | Description                          | Date       |
| -------- | ------------------------------------ | ---------- |
| `001`    | Initial schema (all tables)          | —          |
| `002`    | Add `currency` column to `hotels`    | 2026-03-18 |

---

## Known Gaps & Issues

### Authorization

1. **Admin routes not protected:** `AdminUser` / `require_admin` dependency is defined in `dependencies.py` but **never used** in any route module. All admin endpoints (`/api/v1/admin/*`) only require `CurrentUser`, meaning **any authenticated user** can access admin dashboard stats, manage users, and update bookings.

2. **Catalog mutation routes not protected:** Hotel, tour, room, and promo code CRUD endpoints only require `CurrentUser` — any logged-in user can create/update/delete hotels, tours, rooms, and promo codes.

3. **Frontend admin routes not restricted:** `ProtectedRoute` component supports a `requireAdmin` prop, but the router **never passes** `requireAdmin={true}` for admin routes. Any logged-in user can navigate to `/admin/*`.

4. **Navbar shows Dashboard to all users:** The Dashboard link in both desktop and mobile navigation menus is visible to all authenticated users regardless of role.

### Payments

5. **Payment model missing tour booking FK:** The `Payment` model only has a foreign key to `bookings` (hotel bookings). While `payment_service.create_payment_intent()` accepts `tour_booking_id`, the DB model has no `tour_booking_id` column — tour booking payments are only tracked via Stripe metadata.

6. **Payment endpoints weakly scoped:** `GET /api/v1/payments/{payment_id}` and `DELETE /api/v1/payments/{payment_id}` (refund) do not verify the payment belongs to the current user's booking.

7. **BookingPage imports `paymentsApi` but doesn't use Stripe Elements flow:** The booking page creates a booking directly via `bookingsApi.create()` rather than going through Stripe payment first. The `paymentsApi` import appears unused.

### Email

8. **Password reset email is a placeholder:** `_send_reset_email()` in `auth.py` only logs the reset link. Despite `aiosmtplib` and `Jinja2` being in `requirements.txt`, no actual email sending is implemented.

9. **Config mismatch:** `.env.example` documents SMTP variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`), but `config.py` defines `SENDGRID_API_KEY` instead. These are not aligned.

### Rate Limiting

10. **`app.state.limiter` not set:** slowapi typically requires `app.state.limiter = limiter` for proper integration. This is missing from `main.py`, which may cause issues with rate limiting enforcement.

### Code Quality

11. **Dead code:** `frontend/src/App.jsx` and `frontend/src/App.css` are the default Vite template files. `main.jsx` does not import `App.jsx` — the app routes through `RouterProvider` directly.

12. **Unused dependency:** `class-variance-authority` is installed in `package.json` but never imported or used in any source file.

13. **No database seeds:** No seed scripts or seed migrations exist for initial test data.

14. **No root README:** The project has no `README.md` at the repository root. Documentation lives in `Instruction/`.

15. **`frontend-temp/` directory:** A minimal Vite + React scaffold exists at the repo root but is not wired to `docker-compose.yml` and appears unused.

16. **Package name mismatch:** `frontend/package.json` has `"name": "frontend-tmp"` — likely from an earlier rename without updating the manifest.

---

## Summary of All Features

1. **User Authentication** — Register, login, logout, JWT token rotation with Redis blacklisting, password reset (token generation works, email sending is placeholder)
2. **Hotel Search & Browse** — Full-text search, filters (city, price, stars, amenities, dates, guests, property type), sorting, pagination, infinite scroll
3. **Hotel Details** — Image gallery, amenities, description, available rooms, reviews, interactive map (Leaflet)
4. **Room Availability** — Real-time availability check with date overlap detection and `SELECT ... FOR UPDATE` locking
5. **Hotel Booking** — Guest details, date selection, promo code application (validates via API), price calculation, atomic booking with row-level locking
6. **Booking Confirmation** — Success page with animated checkmark, reference code, copy-to-clipboard, PDF download (jsPDF)
7. **Tour Search & Browse** — Category filter, text search, price filter, sorting, infinite scroll
8. **Tour Details** — Image gallery, highlights, day-by-day itinerary, includes/excludes, reviews, interactive map (Leaflet)
9. **Tour Booking** — Date selection, participant count, capacity enforcement with row locking, price calculation
10. **Payments** — Stripe PaymentIntent + webhooks for status updates (service layer supports hotel + tour bookings; DB model only links hotel bookings)
11. **Reviews** — Star ratings + comments for hotels and tours (requires completed booking), recalculates entity ratings on change
12. **Wishlists** — Save hotels/tours to personal wishlist, view & remove from profile
13. **Promo Codes** — Percentage discounts with validation (expiry, usage limits, minimum amount), applied during booking
14. **Loyalty Points** — Points earned per dollar spent (on payment success), tiered system (Bronze/Silver/Gold/Platinum) with progress bar
15. **User Profile** — 6-tab profile page: edit profile, view bookings (hotel + tour sub-tabs), reviews, wishlist, loyalty status, change password
16. **Admin Dashboard** — Revenue stats, booking analytics, occupancy rates, daily revenue charts (Recharts), recent bookings, filterable by period (week/month/year)
17. **Admin Management** — CRUD for hotels (with image upload/reorder/thumbnail), rooms, tours, bookings (status update), users (search/edit/delete)
18. **Image Uploads** — Cloudinary integration for hotel, room, and tour images; frontend image management with preview, reorder, and thumbnail selection
19. **Search Suggestions** — Debounced hotel suggestions dropdown in SearchBar (React Query + useDebounce)
20. **Currency Display** — Currency picker in Navbar (USD/VND), hotel model supports currency field, admin can set currency per hotel
21. **Rate Limiting** — slowapi rate limiting on auth endpoints (register, login, refresh, password reset)
22. **Token Security** — Redis-based refresh token blacklisting, HTTP-only cookies, SameSite strict, token rotation on refresh
23. **SEO / Meta Tags** — react-helmet-async for per-page title and description tags, Open Graph meta tags on HomePage
24. **Toast Notifications** — Sonner toast system (top-right, rich colors, close button) for success/error feedback throughout the UI
25. **Animations** — Framer Motion page transitions (PageTransition), card entrance animations (AnimatedCard), booking confirmation animation
26. **Error Handling** — React ErrorBoundary component wrapping all pages, global backend exception handler, axios 401 auto-refresh interceptor
27. **Responsive Design** — Mobile hamburger menu, responsive grids, overflow scroll for destinations, sticky navigation
28. **Accessibility** — `:focus-visible` outlines, `.sr-only` utility, aria-labels on icon buttons
29. **Testing** — Backend: pytest + pytest-asyncio (auth, hotels, bookings); Frontend: Vitest + Testing Library (components & utils)
30. **Developer Tooling** — Docker Compose full stack, pgAdmin UI, Vite dev proxy, ESLint (flat config), path aliases (`@` → `./src`), hot reload on both frontend and backend
