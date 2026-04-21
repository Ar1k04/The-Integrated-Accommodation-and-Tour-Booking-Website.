21 April 2026
# Integrated Accommodation & Tour Booking Website
> Graduation Project — Nguyễn Hoàng Bảo Long (22BA13204)
> University of Science & Technology of Hanoi — AY 2025-2026

---

## Project Overview

A full-stack travel booking platform where users can search, compare, and book hotel rooms, tour packages, and flight tickets. The system acts as a trusted intermediary — ensuring secure transactions for customers and providing management dashboards for Admins and Partners (Hotel Owners / Tour Operators).

---

## Tech Stack

| Layer      | Technology                                         |
|------------|----------------------------------------------------|
| Frontend   | React.js, JavaScript, HTML, CSS                    |
| Backend    | Python — FastAPI, Pydantic, SQLAlchemy (async)     |
| Database   | PostgreSQL (17 tables — see schema below)          |
| Cache      | Redis — session management + soft-lock (TTL 15min) |
| Storage    | Cloudinary — images & file uploads                 |
| Auth       | JWT (access + refresh token)                       |

---

## User Roles

| Role     | Permissions |
|----------|-------------|
| Guest    | Browse hotels, tours, flights — no login required |
| Customer | Search, book, pay, manage loyalty points & vouchers, write reviews |
| Partner  | Manage own listings (rooms, tours), inventory, local vouchers, bookings |
| Admin    | Full platform control: users, tiers, global vouchers, reports, partner approval |

> **Inheritance rule:** Customer inherits all Guest capabilities. See `usecase_diagram.puml` for full actor–use case mapping.

---

## External Agent Services

### Hotel — LiteAPI
- Base URL: `https://api.liteapi.travel/v3.0`
- Auth: `X-API-Key` header
- Sandbox key: `sand_c1887765-8c40-40a7-b964-79eee6e3d99a`
- Key endpoints:
  - `GET  /data/hotels`    — search hotels
  - `GET  /data/rooms`     — room types, images, amenities
  - `POST /hotels/rates`   — real-time pricing & availability
  - `POST /hotels/prebook` — confirm price before payment
  - `POST /hotels/book`    — create booking, returns `bookingId`
  - `GET  /bookings/{id}`  — retrieve booking detail
- Use `roomMapping: true` to link a rate to a specific room

### Flight — Duffel
- Base URL: `https://api.duffel.com`
- Auth: `Authorization: Bearer <token>` + `Duffel-Version: v2`
- Sandbox: test token, virtual airline "Duffel Airways" (IATA: ZZ)
- Key endpoints:
  - `POST /air/offer_requests` — search flights
  - `GET  /air/offers`         — list offers with pricing
  - `POST /air/orders`         — book flight, returns `order_id`
  - `GET  /air/orders/{id}`    — booking detail
  - `POST /air/cancellations`  — cancel & refund

### Tour — Viator
- Base URL: `https://api.viator.com/partner`
- Auth: `exp-api-key` header
- Sandbox: free affiliate key
- Key endpoints:
  - `POST /products/search`     — search tours by location/date
  - `GET  /products/{code}`     — tour detail, gallery, itinerary
  - `POST /availability/check`  — check available slots
  - `POST /bookings/book`       — book tour
  - `DELETE /bookings/cancel`   — cancel booking
- **Note:** Viator has no voucher API — vouchers are platform-managed only

---

## Payment

### Stripe (International)
- SDK: `stripe` Python package
- Sandbox test card: `4242 4242 4242 4242`
- Flow: Create `PaymentIntent` → Confirm → Webhook verification
- Webhook events: `payment_intent.succeeded`, `payment_intent.payment_failed`

### VNPay (Domestic)
- Sandbox: `https://sandbox.vnpayment.vn`
- Credentials: `vnp_TmnCode: JVNWOIL0`, `vnp_HashSecret` (from registration email)
- Test card NCB: `9704198526191432198` / OTP: `123456`
- ⚠️ Requires a public URL for IPN callback — use `ngrok http 8000` in local dev
- Flow: Build `vnp_PaymentURL` → Redirect user → Receive IPN → Verify HMAC-SHA512

---

## Database Schema (17 tables)

```
loyalty_tier       — Bronze / Silver / Gold / Platinum tiers
users              — customers + admins + partners; FK → loyalty_tier
hotel              — property listing; liteapi_hotel_id for API calls
room               — room type; liteapi_room_id for API calls
room_image         — Cloudinary URLs for rooms
room_availability  — per-day status: available | booked | blocked; UNIQUE(room_id, date)
tour               — tour listing; viator_product_code for API calls
tour_image         — Cloudinary URLs for tours
tour_schedule      — tour slots per date; UNIQUE(tour_id, available_date)
flight_booking     — Duffel order snapshot; duffel_order_id UNIQUE
voucher            — platform-managed discount codes (percentage | fixed)
booking            — order header; 1 booking → many booking_items
booking_item       — line items: item_type ∈ {room, tour, flight}
payment            — 1-to-1 with booking; provider ∈ {stripe, vnpay}
voucher_usage      — usage log; UNIQUE(voucher_id, user_id) prevents reuse
loyalty_transaction — points ledger: positive = earn, negative = redeem
review             — verified-purchase review (requires booking_item.status = completed)
```

Reference SQL file: `docs/Project.sql`

---

## Key Business Rules

1. **Concurrency control:** Redis TTL 15 min soft-locks a room/tour/flight slot during checkout. PostgreSQL `SELECT FOR UPDATE` prevents double-booking at the DB layer.
2. **Voucher validation:** Always validate voucher in the platform DB before calling any external API. External APIs do not accept voucher codes.
3. **Loyalty points:** Points are credited only after `payment.status = success`. Redemption is stored as a negative value in `loyalty_transaction.points`.
4. **Review gate:** A user may only review a booking item when `booking_item.status = completed`.
5. **Payment routing:** `provider: stripe` → `StripeService`; `provider: vnpay` → `VNPayService`. Both implement the same interface (Strategy Pattern).
6. **API responses:** Always return `{"data": ..., "message": ..., "status": ...}`.
7. **Error handling:** Use FastAPI `HTTPException` with standard HTTP status codes.
8. **Async everywhere:** All DB queries and external API calls must use `async/await`.
9. **Environment variables:** Never hardcode API keys — always read from `.env` via `python-dotenv`.

---

## Project Structure

```
booking-project/
├── CLAUDE.md                        ← this file
├── docs/
│   ├── Project.sql                  ← full DB schema (17 tables)
│   ├── usecase_diagram.puml
│   └── system_architecture.puml
├── backend/
│   ├── main.py
│   ├── core/
│   │   ├── config.py                ← env vars & settings
│   │   ├── database.py              ← async PostgreSQL (SQLAlchemy)
│   │   └── redis.py                 ← Redis connection
│   ├── models/                      ← SQLAlchemy ORM models (mirror Project.sql)
│   ├── schemas/                     ← Pydantic request/response schemas
│   ├── routers/
│   │   ├── auth.py                  ← register, login, refresh token
│   │   ├── hotels.py                ← calls LiteAPI
│   │   ├── flights.py               ← calls Duffel
│   │   ├── tours.py                 ← calls Viator
│   │   ├── bookings.py              ← cart, checkout, history, cancel
│   │   ├── payments.py              ← Stripe + VNPay routing
│   │   ├── vouchers.py              ← apply & validate vouchers
│   │   ├── loyalty.py               ← points, tier, redeem
│   │   └── reviews.py               ← write & read reviews
│   ├── services/
│   │   ├── liteapi_service.py
│   │   ├── duffel_service.py
│   │   ├── viator_service.py
│   │   ├── stripe_service.py
│   │   └── vnpay_service.py
│   └── migrations/                  ← Alembic migrations
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── services/                ← Axios API calls
│   │   └── store/                   ← state management (Redux / Zustand)
│   └── public/
└── docker-compose.yml               ← PostgreSQL + Redis local
```

---

## Code Review Checklist

When reviewing existing code, check the following against this architecture:

### Backend
- [ ] All SQLAlchemy models match the 17 tables in `Project.sql` (column names, types, constraints, FKs)
- [ ] `hotel.admin_id`, `tour.admin_id`, `voucher.admin_id` — FKs reference `users.id`
- [ ] `booking_item.item_type` enum enforced: only `room | tour | flight`
- [ ] Nullable FK columns (`room_id`, `tour_schedule_id`, `flight_booking_id` in `booking_item`) are conditional on `item_type`
- [ ] `room_availability` has UNIQUE constraint on `(room_id, date)`
- [ ] `tour_schedule` has UNIQUE constraint on `(tour_id, available_date)`
- [ ] `voucher_usage` has UNIQUE constraint on `(voucher_id, user_id)`
- [ ] Redis soft-lock implemented in booking flow (TTL 15 min)
- [ ] `SELECT FOR UPDATE` used when confirming inventory
- [ ] Payment routing uses Strategy Pattern (common interface for Stripe & VNPay)
- [ ] All external API calls are async and wrap keys from `.env`
- [ ] All responses follow `{"data": ..., "message": ..., "status": ...}` format
- [ ] JWT auth applied to all protected routes

### Frontend
- [ ] React Router used for client-side navigation
- [ ] Auth state (access token + refresh token) stored securely
- [ ] Booking flow: Search → Filter → View Detail → Select Dates → Add to Cart → Checkout → Payment
- [ ] Guest can browse without login; redirect to login only at checkout
- [ ] Partner Dashboard routes are role-gated
- [ ] Admin Dashboard routes are role-gated

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Database migrations
alembic upgrade head

# Local Redis
docker run -d -p 6379:6379 redis:alpine

# ngrok (required for VNPay IPN callback in local dev)
ngrok http 8000
```

---

## Coding Conventions

- **Language:** Code and comments in English
- **API responses:** Always `{"data": ..., "message": ..., "status": ...}`
- **Error handling:** `HTTPException` with standard HTTP status codes
- **Async:** `async/await` for all DB and external API calls
- **Secrets:** Read from `.env` via `python-dotenv` — never hardcode
- **Lint:** Follow PEP 8 for Python; ESLint + Prettier for JavaScript/React
