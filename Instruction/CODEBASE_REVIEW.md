# Travel Booking Website — Complete Codebase Review

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
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
- [Frontend Pages & Components](#frontend-pages--components)
- [Frontend State Management](#frontend-state-management)
- [Frontend API Layer](#frontend-api-layer)
- [Utilities & Hooks](#utilities--hooks)
- [Infrastructure](#infrastructure)

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

The project is a **full-stack travel booking website** that allows users to search and book hotels and tours. It includes an admin dashboard for managing all entities.

---

## Tech Stack

| Layer        | Technology                                                        |
| ------------ | ----------------------------------------------------------------- |
| **Frontend** | React 18, Vite, TailwindCSS, Zustand, React Query, React Router  |
| **Backend**  | Python, FastAPI, SQLAlchemy 2.0 (async), Alembic                  |
| **Database** | PostgreSQL 15 (via asyncpg)                                       |
| **Cache**    | Redis 7 (token blacklist)                                         |
| **Payments** | Stripe (PaymentIntents + Webhooks)                                |
| **Storage**  | Cloudinary (image uploads)                                        |
| **Auth**     | JWT (access + refresh tokens), bcrypt password hashing            |
| **Infra**    | Docker Compose (postgres, redis, backend, frontend, pgadmin)      |

---

## Database Models

Every model inherits from `Base` which provides:
- `id` — UUID primary key (auto-generated)
- `created_at` — timestamp with timezone
- `updated_at` — timestamp with timezone (auto-updates)

### User

| Field             | Type         | Notes                              |
| ----------------- | ------------ | ---------------------------------- |
| `email`           | String(255)  | Unique, indexed                    |
| `hashed_password` | String(255)  | bcrypt hash (SHA-256 pre-hashed)   |
| `full_name`       | String(255)  |                                    |
| `phone`           | String(50)   | Optional                           |
| `avatar_url`      | Text         | Optional                           |
| `role`            | String(20)   | `"user"` or `"admin"`              |
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
| `property_type` | String(50)    | Optional                         |
| `amenities`     | JSONB         | Array of amenity strings         |
| `images`        | JSONB         | Array of image URLs              |
| `base_price`    | Numeric(10,2) |                                  |
| `avg_rating`    | Float         | Computed from reviews            |
| `total_reviews` | Integer       | Computed from reviews            |

**Relationships:** rooms, reviews

### Room

| Field             | Type          | Notes                        |
| ----------------- | ------------- | ---------------------------- |
| `hotel_id`        | UUID (FK)     | References `hotels.id`       |
| `name`            | String(255)   |                              |
| `description`     | Text          | Optional                     |
| `room_type`       | String(50)    | single/double/suite/family/villa |
| `price_per_night` | Numeric(10,2) |                              |
| `total_quantity`   | Integer       | Default `1`                  |
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
| `booking_id`               | UUID (FK)     | Optional, references `bookings.id` |
| `stripe_payment_intent_id` | String(255)   | Unique, from Stripe                |
| `amount`                   | Numeric(10,2) |                                    |
| `currency`                 | String(10)    | Default `"usd"`                    |
| `status`                   | String(20)    | `pending` / `succeeded` / `failed` / `refunded` |

**Relationships:** booking

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
| POST   | `/password/forgot`    | Public   | 3/min      | Send password reset email (placeholder)        |
| POST   | `/password/reset`     | Public   | 5/min      | Reset password using token from email          |
| GET    | `/me`                 | User     | —          | Get current user profile                       |
| PATCH  | `/me`                 | User     | —          | Update current user profile (name, phone, etc) |

**Token flow:**
- Access token: JWT in `Authorization: Bearer <token>` header, expires in 15 minutes
- Refresh token: HTTP-only cookie (`refresh_token`), expires in 7 days
- Refresh token blacklisting via Redis to prevent reuse
- Password hashing: SHA-256 pre-hash → bcrypt

### 2. Hotels (`/api/v1/hotels`)

| Method | Endpoint              | Auth  | Description                                            |
| ------ | --------------------- | ----- | ------------------------------------------------------ |
| GET    | `/`                   | Public| List hotels with filtering, sorting, pagination         |
| GET    | `/{hotel_id}`         | Public| Get single hotel details                                |
| POST   | `/`                   | Admin | Create a new hotel                                      |
| PUT    | `/{hotel_id}`         | Admin | Full replace of hotel data                              |
| PATCH  | `/{hotel_id}`         | Admin | Partial update of hotel data                            |
| DELETE | `/{hotel_id}`         | Admin | Delete a hotel (cascades to rooms)                      |
| POST   | `/{hotel_id}/images`  | Admin | Upload images to Cloudinary, append URLs to hotel       |

**List filters:** `city`, `country`, `check_in`/`check_out` (availability), `guests`, `min_price`, `max_price`, `star_rating`, `amenities` (comma-separated), `property_type`, `search` (text search on name/description)

**Sorting:** `created_at`, `base_price`, `avg_rating`, `star_rating`, `name` (asc/desc)

**Availability logic:** Filters out hotels where all rooms are booked (status `pending`/`confirmed`) during the requested dates.

### 3. Rooms (`/api/v1/rooms`)

| Method | Endpoint                            | Auth  | Description                               |
| ------ | ----------------------------------- | ----- | ----------------------------------------- |
| GET    | `/hotels/{hotel_id}/rooms`          | Public| List rooms for a hotel (with availability) |
| POST   | `/hotels/{hotel_id}/rooms`          | Admin | Create a room for a hotel                  |
| GET    | `/rooms/{room_id}`                  | Public| Get single room details                    |
| PUT    | `/rooms/{room_id}`                  | Admin | Full replace of room data                  |
| PATCH  | `/rooms/{room_id}`                  | Admin | Partial update of room data                |
| DELETE | `/rooms/{room_id}`                  | Admin | Delete a room                              |
| GET    | `/rooms/{room_id}/availability`     | Public| Check if room is available for dates       |
| POST   | `/rooms/{room_id}/images`           | Admin | Upload images to Cloudinary for room       |

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

| Method | Endpoint             | Auth  | Description                                  |
| ------ | -------------------- | ----- | -------------------------------------------- |
| GET    | `/`                  | Public| List tours with filtering, sorting, pagination|
| GET    | `/{tour_id}`         | Public| Get single tour details                       |
| POST   | `/`                  | Admin | Create a new tour                             |
| PUT    | `/{tour_id}`         | Admin | Full replace of tour data                     |
| PATCH  | `/{tour_id}`         | Admin | Partial update of tour data                   |
| DELETE | `/{tour_id}`         | Admin | Delete a tour                                 |
| POST   | `/{tour_id}/images`  | Admin | Upload images to Cloudinary for tour          |

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
| DELETE | `/reviews/{review_id}`         | User/Admin | Delete review (owner or admin)        |

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
| POST   | `/webhooks`       | Stripe| Handle Stripe webhook events                    |
| DELETE | `/{payment_id}`   | Admin | Issue a full refund via Stripe                  |

**Payment flow:**
1. `create_payment_intent`: Creates Stripe PaymentIntent, stores local `Payment` record, returns `client_secret`
2. Frontend uses `client_secret` to complete payment via Stripe.js
3. Stripe sends webhook → `handle_webhook_event`:
   - `payment_intent.succeeded` → updates Payment status, sets Booking to `confirmed`, awards loyalty points
   - `payment_intent.payment_failed` → updates Payment status to `failed`
4. Refund: Calls `stripe.Refund.create()`, sets Payment to `refunded`, Booking to `cancelled`

**Loyalty points:** 1 point per $1 spent (awarded on successful payment)

### 9. Wishlists (`/api/v1/wishlists`)

| Method | Endpoint            | Auth | Description                           |
| ------ | ------------------- | ---- | ------------------------------------- |
| GET    | `/`                 | User | List current user's wishlisted items   |
| POST   | `/`                 | User | Add a hotel or tour to wishlist        |
| DELETE | `/{wishlist_id}`    | User | Remove item from wishlist              |

**Rules:** Must provide exactly one of `hotel_id` or `tour_id`. Duplicate entries are rejected (409 Conflict).

### 10. Promo Codes (`/api/v1/promo-codes`)

| Method | Endpoint          | Auth  | Description                                   |
| ------ | ----------------- | ----- | --------------------------------------------- |
| POST   | `/validate`       | User  | Validate a promo code against a booking amount |
| POST   | `/`               | Admin | Create a new promo code                        |
| GET    | `/`               | Admin | List all promo codes (paginated)               |
| PATCH  | `/{promo_id}`     | Admin | Update a promo code                            |
| DELETE | `/{promo_id}`     | Admin | Delete a promo code                            |

**Validation checks:** Code exists, is active, not expired, not at max uses, booking amount >= minimum.

### 11. Admin (`/api/v1/admin`)

| Method | Endpoint               | Auth  | Description                                    |
| ------ | ---------------------- | ----- | ---------------------------------------------- |
| GET    | `/stats`               | Admin | Dashboard statistics (revenue, bookings, users) |
| GET    | `/users`               | Admin | List all users (searchable, paginated)          |
| GET    | `/users/{user_id}`     | Admin | Get user details                                |
| PATCH  | `/users/{user_id}`     | Admin | Update user (role, active status, etc.)         |
| DELETE | `/users/{user_id}`     | Admin | Delete a user                                   |
| GET    | `/bookings`            | Admin | List all hotel bookings (filterable, paginated) |
| PATCH  | `/bookings/{booking_id}` | Admin | Update booking status                         |

**Dashboard stats (by period: week/month/year):**
- `total_revenue` — sum of succeeded payments
- `bookings_count` — total hotel bookings created
- `new_users` — newly registered users
- `occupancy_rate` — booked rooms / total rooms (%)
- `revenue_chart_data` — daily revenue breakdown
- `bookings_by_status` — count per status (pending, confirmed, etc.)
- `recent_bookings` — last 10 bookings

---

## Backend Services (Business Logic)

### auth_service.py
| Function                     | Description                                              |
| ---------------------------- | -------------------------------------------------------- |
| `register_user(db, data)`    | Checks email uniqueness, hashes password, creates User   |
| `authenticate_user(db, email, password)` | Verifies credentials, checks account active   |
| `issue_tokens(user_id, role)` | Creates access + refresh JWT pair                       |
| `blacklist_token(redis, jti)` | Adds token JTI to Redis blacklist with TTL              |
| `is_token_blacklisted(redis, jti)` | Checks if token JTI is blacklisted              |
| `validate_refresh_token(redis, token)` | Decodes token, checks type & blacklist       |
| `create_password_reset_token(user_id)` | Creates 1-hour JWT for password reset        |
| `verify_password_reset_token(token)` | Validates reset token, returns user_id         |
| `reset_user_password(db, user_id, new_password)` | Updates user's hashed password     |

### security.py
| Function                      | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `hash_password(password)`     | SHA-256 pre-hash → bcrypt hash                          |
| `verify_password(plain, hashed)` | Verifies password against bcrypt hash                |
| `create_access_token(subject, extra)` | Creates JWT access token (15 min expiry)        |
| `create_refresh_token(subject)` | Creates JWT refresh token (7 day expiry) with JTI     |
| `decode_token(token)`         | Decodes and validates JWT                               |

### availability_service.py
| Function                      | Description                                             |
| ----------------------------- | ------------------------------------------------------- |
| `check_and_reserve(db, ...)`  | Atomically checks room availability and creates booking with row-level locking (`FOR UPDATE`) |
| `_promo_is_valid(promo, amount)` | Validates promo code (expiry, uses, min amount)      |

### payment_service.py
| Function                          | Description                                         |
| --------------------------------- | --------------------------------------------------- |
| `create_payment_intent(db, ...)`  | Creates Stripe PaymentIntent, stores local Payment   |
| `handle_webhook_event(db, event)` | Processes Stripe webhooks (succeeded/failed)         |
| `refund_payment(db, payment_id)`  | Issues Stripe refund, cancels booking                |
| `_award_loyalty_points(db, user_id, amount)` | Awards 1 point per $1 to user          |

### cloudinary_service.py
| Function                        | Description                                           |
| ------------------------------- | ----------------------------------------------------- |
| `upload_image(file, folder)`    | Uploads single image to Cloudinary, returns URL        |
| `upload_images(files, folder)`  | Uploads multiple images, returns list of URLs          |

### dependencies.py
| Function              | Description                                                 |
| --------------------- | ----------------------------------------------------------- |
| `get_current_user(db, ...)` | Extracts user from Bearer header or cookie, validates JWT |
| `require_admin(current_user)` | Ensures user has `admin` role                          |
| `CurrentUser`         | Type alias for dependency-injected authenticated user       |
| `AdminUser`           | Type alias for dependency-injected admin user               |

---

## Frontend Pages & Components

### Pages

| Page                     | Route                       | Auth     | Description                                          |
| ------------------------ | --------------------------- | -------- | ---------------------------------------------------- |
| `HomePage`               | `/`                         | Public   | Hero search bar, featured destinations, popular hotels, top tours, value propositions |
| `LoginPage`              | `/login`                    | Public   | Email/password login form                            |
| `RegisterPage`           | `/register`                 | Public   | Registration form (name, email, password, phone)     |
| `SearchResultsPage`      | `/hotels/search`            | Public   | Hotel search with filters (price, stars, amenities), sorting, infinite scroll |
| `HotelDetailPage`        | `/hotels/:id`               | Public   | Hotel info, image gallery, amenities, available rooms, reviews, reserve button |
| `BookingPage`            | `/bookings/new`             | User     | Guest details form, date selection, promo code input, price breakdown, booking creation |
| `BookingConfirmationPage`| `/bookings/:id/confirmation`| User     | Success screen with booking reference, details, PDF download |
| `ToursPage`              | `/tours`                    | Public   | Tour listing with category filter, search, price filter, sorting, infinite scroll |
| `TourDetailPage`         | `/tours/:id`                | Public   | Tour info, image gallery, highlights, itinerary, includes/excludes, reviews, booking panel |
| `ProfilePage`            | `/profile`                  | User     | Tabbed profile page (6 tabs — see below)             |
| `MyBookingsPage`         | `/my-bookings`              | User     | Redirects to `/profile?tab=bookings`                 |
| `AdminDashboard`         | `/admin`                    | Admin    | Stats dashboard (revenue, bookings, occupancy, charts)|
| `ManageHotels`           | `/admin/hotels`             | Admin    | CRUD table for hotels                                |
| `ManageRooms`            | `/admin/rooms`              | Admin    | CRUD table for rooms                                 |
| `ManageTours`            | `/admin/tours`              | Admin    | CRUD table for tours                                 |
| `ManageBookings`         | `/admin/bookings`           | Admin    | View/update booking statuses                         |
| `ManageUsers`            | `/admin/users`              | Admin    | View/update/delete users                             |

### ProfilePage Tabs

| Tab        | Description                                                        |
| ---------- | ------------------------------------------------------------------ |
| Profile    | Edit name, email, phone; avatar display                            |
| Bookings   | Sub-tabs for hotel bookings and tour bookings; cancel pending ones |
| Reviews    | List all user's reviews; delete option                             |
| Wishlist   | List wishlisted hotels/tours; remove option                        |
| Loyalty    | Points display, tier progress (Bronze/Silver/Gold/Platinum), earning rules |
| Security   | Change password form                                               |

### Reusable Components

| Component           | Location                        | Description                                       |
| ------------------- | ------------------------------- | ------------------------------------------------- |
| `AppLayout`         | `components/common/`            | Main layout with Navbar + Footer + Outlet          |
| `Navbar`            | `components/common/`            | Top navigation bar with auth links                 |
| `Footer`            | `components/common/`            | Site footer                                        |
| `SearchBar`         | `components/common/`            | Destination/date/guest search bar (hero & compact) |
| `ProtectedRoute`    | `components/common/`            | Auth guard, optional `requireAdmin` prop           |
| `Breadcrumb`        | `components/common/`            | Navigation breadcrumbs                             |
| `PriceBreakdown`    | `components/common/`            | Price calculation display (nights × rate - discount)|
| `BookingStatusBadge`| `components/common/`            | Colored status badge (pending/confirmed/etc.)      |
| `StarRating`        | `components/common/`            | Star rating display                                |
| `Skeleton`          | `components/common/`            | Loading skeleton components                        |
| `AnimatedCard`      | `components/common/`            | Card with entrance animation                       |
| `EmptyState`        | `components/common/`            | Empty content placeholder                          |
| `ErrorBoundary`     | `components/common/`            | React error boundary                               |
| `PageTransition`    | `components/common/`            | Page transition animation wrapper                  |
| `HotelCard`         | `components/hotel/`             | Hotel listing card (image, price, rating, location)|
| `HotelFilters`      | `components/hotel/`             | Sidebar filter panel for hotel search              |
| `ImageGallery`      | `components/hotel/`             | Image gallery/carousel                             |
| `TourCard`          | `components/tour/`              | Tour listing card (image, price, duration, rating) |
| `RoomCard`          | `components/room/`              | Room card with details and reserve button          |
| `ReviewCard`        | `components/review/`            | Single review display (user, rating, comment)      |
| `ReviewForm`        | `components/review/`            | Form to submit a review (rating + comment)         |

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
| `initialize()`     | Called on app load — attempts to refresh token                 |

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

---

## Frontend API Layer

All API calls go through `axiosInstance.js` which:
1. Sets base URL to `VITE_API_BASE_URL` (or `/api/v1`)
2. Sends `withCredentials: true` (for refresh cookie)
3. Attaches `Authorization: Bearer <token>` from auth store
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
| `paymentsApi`   | `create`, `get`, `refund`                                            |
| `reviewsApi`    | `listHotelReviews`, `listTourReviews`, `create`, `update`, `delete`  |
| `adminApi`      | `getStats`, `listUsers`, `getUser`, `updateUser`, `deleteUser`, `listBookings`, `updateBooking`, `listPromoCodes`, `createPromoCode`, `updatePromoCode`, `deletePromoCode`, `validatePromoCode`, `listWishlists`, `addToWishlist`, `removeFromWishlist` |

---

## Utilities & Hooks

### Utility Functions (`utils/`)

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

### Constants (`utils/constants.js`)

| Constant          | Value                                                                    |
| ----------------- | ------------------------------------------------------------------------ |
| `ROOM_TYPES`      | `['single', 'double', 'suite', 'family', 'villa']`                      |
| `TOUR_CATEGORIES` | `['adventure', 'cultural', 'beach', 'city', 'nature', 'food']`          |
| `AMENITIES`       | 13 amenities (wifi, pool, gym, spa, parking, restaurant, bar, etc.)      |
| `BOOKING_STATUSES`| `['pending', 'confirmed', 'cancelled', 'completed']`                     |
| `CURRENCIES`      | USD and VND                                                              |
| `ITEMS_PER_PAGE`  | `20`                                                                     |

### Custom Hooks (`hooks/`)

| Hook               | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `useAuth()`        | Convenience wrapper around `authStore` — returns `user`, `isAuthenticated`, `isAdmin`, `login`, `logout`, `register`, `refreshToken`, `updateProfile` |
| `useDebounce(value, delay)` | Debounces a value by `delay` ms (default 300ms)           |
| `useInfiniteScroll(callback, options)` | IntersectionObserver-based infinite scroll trigger |

---

## Infrastructure

### Docker Compose Services

| Service      | Image              | Port  | Purpose                           |
| ------------ | ------------------ | ----- | --------------------------------- |
| `postgres`   | postgres:15-alpine | 5432  | Primary database                  |
| `redis`      | redis:7-alpine     | 6379  | Token blacklist cache             |
| `backend`    | Custom Dockerfile  | 8000  | FastAPI application               |
| `frontend`   | Custom Dockerfile  | 5173  | Vite React dev server             |
| `pgadmin`    | dpage/pgadmin4     | (env) | Database admin UI                 |

### Environment Variables (`.env`)

Key configuration:
- `DATABASE_URL` — PostgreSQL async connection string
- `REDIS_URL` — Redis connection string
- `SECRET_KEY` — JWT signing secret
- `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` — Stripe integration
- `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` — Image uploads
- `FRONTEND_URL` — CORS origin (default: `http://localhost:5173`)

### Database Migrations

Managed by **Alembic** with an initial schema migration at `alembic/versions/001_initial_schema.py`.

---

## Summary of All Features

1. **User Authentication** — Register, login, logout, JWT token rotation, password reset
2. **Hotel Search & Browse** — Full-text search, filters (city, price, stars, amenities, dates, guests), sorting, pagination, infinite scroll
3. **Hotel Details** — Image gallery, amenities, description, available rooms, reviews
4. **Room Availability** — Real-time availability check with date overlap detection
5. **Hotel Booking** — Guest details, date selection, promo code application, price calculation, atomic booking with row-level locking
6. **Booking Confirmation** — Success page with reference code, PDF download (jsPDF)
7. **Tour Search & Browse** — Category filter, text search, price filter, sorting, infinite scroll
8. **Tour Details** — Image gallery, highlights, day-by-day itinerary, includes/excludes, reviews
9. **Tour Booking** — Date selection, participant count, capacity enforcement, price calculation
10. **Payments** — Stripe PaymentIntent integration with webhooks for status updates
11. **Reviews** — Star ratings + comments for hotels and tours (requires completed booking)
12. **Wishlists** — Save hotels/tours to personal wishlist
13. **Promo Codes** — Percentage discounts with validation (expiry, usage limits, minimum amount)
14. **Loyalty Points** — Points earned per dollar spent, tiered system (Bronze/Silver/Gold/Platinum)
15. **User Profile** — Edit profile, view bookings, reviews, wishlist, loyalty status, change password
16. **Admin Dashboard** — Revenue stats, booking analytics, occupancy rates, revenue charts
17. **Admin Management** — CRUD operations for hotels, rooms, tours, bookings, users, promo codes
18. **Image Uploads** — Cloudinary integration for hotel and tour images
19. **Rate Limiting** — slowapi rate limiting on auth endpoints
20. **Token Security** — Redis-based refresh token blacklisting, HTTP-only cookies
