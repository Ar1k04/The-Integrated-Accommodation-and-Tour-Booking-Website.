# Memory — Session Log

---

## Session 1 — Admin / User Role Separation

### What Was Done

Separated admin and user roles so they have completely different experiences in the app.

| Rule | Implementation |
|------|---------------|
| **User** registers on `/register` page (normal) | No change — stays as-is, role defaults to `"user"` |
| **Admin** registers on `/register` page (collapsible section) | Added a "Register as Admin" collapsible panel below the user registration card on `RegisterPage`, with `role: "admin"` |
| **User** cannot access Dashboard (`/admin/*`) | All admin routes now require `requireAdmin` in `ProtectedRoute`; backend uses `AdminUser` dependency |
| **Admin** can only see Dashboard (`/admin/*`) | Public pages redirect admin to `/admin` via `RedirectIfAdmin`; user-only routes use `userOnly` on `ProtectedRoute` |
| **Admin** gets a dedicated sidebar layout | Created `AdminLayout` with sidebar navigation (replaces `AppLayout` for admin routes) |

### Files Changed

#### Backend
1. **`backend/app/schemas/user.py`** — Added `role` field to `UserCreate` schema (default `"user"`, validates `"user"` or `"admin"`)
2. **`backend/app/services/auth_service.py`** — `register_user()` now uses `data.role` when creating the user
3. **`backend/app/api/v1/routes/admin.py`** — Changed all endpoints from `CurrentUser` to `AdminUser` dependency (returns 403 for non-admins)

#### Frontend
4. **`frontend/src/pages/LoginPage.jsx`** — Clean login-only page. After login, admins redirect to `/admin`, users redirect to the original page or `/`.
5. **`frontend/src/pages/RegisterPage.jsx`** — User registration card on top. Below it, a collapsible "Register as Admin" panel sends `role: 'admin'`.
6. **`frontend/src/components/common/ProtectedRoute.jsx`** — Added `userOnly` prop: if the user is an admin, redirect to `/admin`.
7. **`frontend/src/components/common/RedirectIfAdmin.jsx`** — New component. Wraps public pages; redirects admins to `/admin`.
8. **`frontend/src/components/common/AdminLayout.jsx`** — New component. Dedicated admin layout with a sidebar.
9. **`frontend/src/router/index.jsx`** — Split routes into `AppLayout` (users) and `AdminLayout` (admins).
10. **`frontend/src/components/common/Navbar.jsx`** — Removed Dashboard link from user dropdown (admin uses sidebar).

### Route Access Matrix

| Route | Not logged in | User | Admin |
|-------|:---:|:---:|:---:|
| `/` | Yes | Yes | → `/admin` |
| `/login` | Yes | → `/` | → `/admin` |
| `/profile` | → `/login` | Yes | → `/admin` |
| `/admin/*` | → `/login` | → `/` | Yes |

### Key Architecture Decisions
- Role stored in DB (`users.role`: `"user"` | `"admin"`) and in JWT payload
- `useAuth()` → `isAdmin = user?.role === 'admin'`
- `AdminUser` dependency on backend returns 403 for non-admins
- Two layouts: `AppLayout` (Navbar + Footer) and `AdminLayout` (Sidebar)

---

## Session 2 — Sprint 1: Polymorphic Schema Migration (17-Table Target) 2:34AM 22/4 

### Context
Evolved the project from a 10-table flat schema to the 17-table polymorphic schema defined in `docs/Project.sql`. The directive was "do not rebuild, improve."

### Migrations

**`backend/alembic/versions/005_add_target_schema.py`** — Added 8 new tables and 5 new columns to existing tables:
- New tables: `loyalty_tier`, `loyalty_transaction`, `vouchers`, `voucher_usage`, `room_availability`, `tour_schedule`, `flight_booking`, `booking_item`
- New columns: `users.loyalty_tier_id`, `hotels.liteapi_hotel_id`, `rooms.liteapi_room_id`, `tours.viator_product_code`
- Seeded 4 loyalty tiers: Bronze (0–499, 0%), Silver (500–1499, 5%), Gold (1500–4999, 10%), Platinum (5000+, 15%)

**`backend/alembic/versions/006_migrate_legacy_bookings.py`** — Data migration:
- Existing `bookings` rows → each gets a `booking_item(item_type='room')` child row
- Existing `tour_bookings` rows → new `bookings` row + `booking_item(item_type='tour')` + `tour_schedule` upsert
- Existing `promo_codes` rows → mirrored into `vouchers`
- Users with `loyalty_points > 0` → `loyalty_transaction(type='adjust')` backfill
- Full reversible `downgrade()` included

### New SQLAlchemy Models (`backend/app/models/`)

| File | Description |
|------|-------------|
| `loyalty_tier.py` | Tier definition (name, min/max_points, discount_percent) |
| `loyalty_transaction.py` | Ledger entry (earn / redeem / adjust) |
| `voucher.py` | Voucher (code, discount_type, discount_value, min_order, max_uses, status) |
| `voucher_usage.py` | Per-user usage record; UNIQUE(voucher_id, user_id) |
| `room_availability.py` | Per-date room status (available / booked / blocked) |
| `tour_schedule.py` | Per-date tour slots (total_slots, booked_slots) |
| `flight_booking.py` | Duffel flight record (duffel_order_id, IATA codes, passenger info) |
| `booking_item.py` | Polymorphic item (item_type: room / tour / flight) |

**Updated models:**
- `user.py` — added `loyalty_tier_id` FK, `loyalty_tier` relationship
- `booking.py` — added `voucher_id`, `discount_amount`, `points_earned`, `points_redeemed`, `items` relationship (selectin)
- `hotel.py` — added `owner_id` FK (partner scoping), `liteapi_hotel_id`
- `tour.py` — added `owner_id` FK, `viator_product_code`
- `room.py` — added `liteapi_room_id`

### New Pydantic Schemas (`backend/app/schemas/`)

| File | Key Types |
|------|-----------|
| `booking_item.py` | `RoomItemCreate` (+ `guests_count`), `TourItemCreate`, `FlightItemCreate`, discriminated union `BookingItemCreate`, `BookingItemResponse` |
| `booking.py` | `BookingCreate {items[], voucher_code, points_to_redeem}`, `LegacyBookingCreate`, `BookingResponse` |
| `voucher.py` | `VoucherCreate/Update/Response`, `VoucherValidateRequest/Response` |
| `loyalty.py` | `LoyaltyTierResponse`, `LoyaltyStatusResponse`, `LoyaltyRedeemRequest/Response` |
| `flight_booking.py` | `FlightBookingCreate/Update/Response` |
| `hotel.py` | `slug` made optional — auto-generated from `name` when omitted |

### New Services (`backend/app/services/`)

**`voucher_service.py`**
- `validate_voucher(db, code, user_id, subtotal)` — checks status, dates, min_order, per-user uniqueness
- `compute_discount(voucher, subtotal)` — percentage or fixed (capped at subtotal)
- `apply_voucher(db, booking, voucher, user_id)` — records `VoucherUsage`, bumps `used_count`, sets `booking.discount_amount`

**`loyalty_service.py`**
- `award_points(db, user_id, booking_id, amount)` — SELECT FOR UPDATE, inserts transaction
- `redeem_points(db, user_id, booking_id, points)` — validates balance, returns `(txn, discount)`
- `recompute_tier(db, user)` — maps `loyalty_points` to correct `LoyaltyTier` row
- `get_status(db, user_id)` — returns tier, points, progress, recent transactions

**`booking_service.py`**
- `create_booking(db, user_id, BookingCreate)` — orchestrates cart: locks inventory, upserts availability rows, applies voucher + loyalty redemption, creates `Booking` + `BookingItem` rows. Sets legacy top-level fields from first room item for backward compat.
- `confirm_booking(db, booking)` — marks confirmed, awards 1pt/$1
- `cancel_booking(db, booking)` — releases tour slots and room_availability rows

**Updated:**
- `auth_service.py` — `register_user` assigns Bronze tier on account creation
- `core/dependencies.py` — added `SuperAdminUser` dependency; `AdminUser` now accepts both `admin` and `superadmin` roles

### New / Updated Routes (`backend/app/api/v1/routes/`)

| File | Change |
|------|--------|
| `bookings.py` | POST detects legacy vs new shape; `_adapt_legacy` maps old `{room_id, check_in, ...}` to `items[]`; DELETE calls `cancel_booking` |
| `vouchers.py` | NEW — `/vouchers/validate` (user), CRUD (admin); non-superadmin scoped by `admin_id` |
| `loyalty.py` | NEW — `GET /loyalty/me` (status), `POST /loyalty/redeem` |
| `promo_codes.py` | Aliased — validate tries voucher first, falls back to legacy; mutations require `AdminUser` |
| `hotels.py` | Mutations require `AdminUser`; `create_hotel` auto-assigns `owner_id`; `_assert_owner_or_superadmin` enforced on PUT/PATCH/DELETE; slug auto-generated if omitted |
| `rooms.py` | `_load_room_and_check` resolves room→hotel→owner; mutations require `AdminUser` |
| `tours.py` | `_assert_tour_owner_or_superadmin` enforced; mutations require `AdminUser` |
| `admin.py` | All endpoints changed from `CurrentUser` → `AdminUser` |
| `payments.py` | `_load_payment_for_user` returns 404 (not 403) for unauthorized access; webhook idempotency via Redis `SET NX EX 604800` on `stripe:webhook:{event_id}` |

**`backend/app/main.py`** — registered `vouchers_router` and `loyalty_router` at `/api/v1`.

### Frontend Changes (`frontend/src/`)

**`components/common/Navbar.jsx`** — Dashboard link in desktop dropdown and mobile menu now gated on `isAdmin` from `useAuth()`.

### Tests (`backend/tests/`)

| File | Coverage |
|------|----------|
| `test_voucher.py` | Happy path, below minimum, expired, duplicate-use blocked, percentage/fixed compute |
| `test_loyalty.py` | Award, redeem, insufficient balance, tier boundaries at 499/500/1500, recompute after redemption, status progress |
| `test_booking_polymorphic.py` | Room+tour cart → 1 booking + 2 items + summed total, oversubscription rejected, cancel releases tour slots |

**`tests/conftest.py`** — Switched from SQLite (incompatible with JSONB) to a dedicated `travel_test_db` PostgreSQL database. Created via `docker exec travel_postgres psql … CREATE DATABASE travel_test_db`.

### Bugs Fixed During Test Run
1. **Price inflation** — legacy adapter was passing `guests_count` as room `quantity`, multiplying the nightly rate by guest count. Fixed by setting `quantity=1` and using a separate `guests_count` field on `RoomItemCreate`.
2. **Missing max-guests validation** — `_reserve_room_item` now raises `BookingServiceError` when `item.guests_count > room.max_guests`.
3. **Hotel slug required** — `HotelCreate.slug` made optional; `create_hotel` route auto-generates it from `name` with a `-N` collision suffix.

### Final Test Result
```
41 passed, 3 warnings in 15.01s
```
Migrations: `alembic upgrade head` and `alembic downgrade 004` both apply cleanly.

### Architecture Decisions
- Service layer is HTTP-agnostic — raises `BookingServiceError / VoucherError / LoyaltyError`; routes translate to `HTTPException`
- Webhook idempotency uses atomic Redis `SET NX` (not exists + set) to prevent race conditions
- Payment 404 (not 403) on unauthorized access prevents existence enumeration
- Legacy `tour_bookings` rows still written alongside new `booking + booking_item` for backward compat until Sprint 2
- `SELECT … FOR UPDATE` used on User (loyalty), Room, and TourSchedule rows during booking

### Out of Scope (queued for Sprint 2+)
- Drop legacy columns (`bookings.room_id`, `promo_codes` table, `tour_bookings` table)
- Voucher + loyalty UI on frontend
- LiteAPI hotel search / Viator tour search (Sprint 3)
- VNPay domestic payment / Duffel flights (Sprint 4)
