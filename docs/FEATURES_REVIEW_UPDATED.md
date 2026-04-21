# TravelBooking — Features Review (Updated)
Last updated: 2026-04-03

This document reviews all major features in the project: backend API capabilities, frontend user flows, and admin/superadmin management behavior.

---

## 1) Core User Roles & Access Control

### Roles
- `user`: can browse/search and create bookings
- `admin`: can manage only the hotels/tours they own
- `superadmin`: can manage hotels/rooms/tours across the whole platform

### Superadmin behavior
- The user `longco6868@gmail.com` is set to `superadmin` via Alembic migration `004_set_superadmin_role.py`.
- Backend ownership checks for hotel/tour/room modifications are bypassed for `superadmin` in:
  - `backend/app/api/v1/routes/hotels.py`
  - `backend/app/api/v1/routes/tours.py`
  - `backend/app/api/v1/routes/rooms.py`
- Frontend admin pages stop filtering by `owner_id` when `user.role === 'superadmin'`:
  - `frontend/src/pages/admin/ManageHotels.jsx`
  - `frontend/src/pages/admin/ManageTours.jsx`
  - `frontend/src/pages/admin/ManageRooms.jsx`

---

## 2) Authentication & Account Management

### Backend
- Register / Login / Logout
- JWT access + refresh token rotation
- Redis refresh token blacklisting on logout/refresh
- `GET /me` to fetch current user profile
- Password reset flow (email sending is currently a logging placeholder)

### Frontend
- Register page
- Login page
- Protected routes based on authentication/role flags from Zustand store
- Profile page supports editing profile, viewing bookings (hotel + tour), reviews, wishlist, loyalty status, and password change

---

## 3) Hotel Domain (Accommodation)

### Hotel Search & Browse
- `GET /hotels` supports:
  - pagination + infinite scroll
  - filters: city, country, star rating, amenities, property type
  - date-based availability filtering using room bookings overlap
  - guest filtering by room `max_guests`
  - price filtering/sorting based on *room pricing* (see Pricing section below)
  - text search: name/description
  - sorting (including “Price”)

### Hotel Details Page
- Displays:
  - image gallery (Cloudinary-backed)
  - amenities, description, location
  - available rooms (with availability rules)
  - guest reviews (hotel reviews list)
  - interactive map (Leaflet)

---

## 4) Room Availability & Hotel Booking Flow

### Room Availability
- `GET /hotels/{hotel_id}/rooms` loads rooms.
- `GET /rooms/{room_id}/availability` returns:
  - `available: bool`
  - `rooms_left` based on overlapping bookings (pending/confirmed).

### Booking Creation
- Users can reserve a room by selecting dates and guests.
- Price calculation includes nights × room price; promo codes are validated via promo-code API.
- Booking creation is performed atomically using row-level locking patterns (per the codebase review notes).

---

## 5) Payments (Stripe)

### Backend
- Stripe PaymentIntent creation for bookings
- Stripe webhook handler updates payment status based on PaymentIntent outcomes
- Refund support via Stripe

### Frontend
- Booking confirmation experience (success UI + confirmation details)
- Stripe flow is integrated via Stripe client libraries (frontend supports the intended flow; backend model currently links payment primarily to hotel bookings).

---

## 6) Hotel Reviews & Wishlists

### Reviews
- Users can create reviews only when they have a completed booking (hotel or tour).
- Exactly one target per review:
  - `hotel_id XOR tour_id`
- Rating updates aggregate into `avg_rating` and `total_reviews`.

### Wishlists
- Users can save either hotels or tours.
- Exactly one target per wishlist:
  - `hotel_id XOR tour_id`

---

## 7) Promo Codes

### Backend
- CRUD for promo codes
- Validation endpoint:
  - expiry checks
  - max uses checks
  - minimum booking amount check
  - discount percent application

### Frontend
- Booking page allows entering a promo code and shows the calculated discount.

---

## 8) Loyalty Points

### Backend / UI
- Loyalty points are awarded based on successful payment amount.
- Loyalty tiers supported:
  - Bronze / Silver / Gold / Platinum
- Profile page shows:
  - current points
  - progress bar toward next tier

---

## 9) Tours Domain

### Tours Search & Browse
- `GET /tours` supports:
  - city/country/category filters
  - text search: name/description
  - price filter/sorting and pagination
  - duration filter
  - infinite scroll usage on the frontend

### Tour Details
- Image gallery, highlights, itinerary, includes/excludes, reviews, interactive map.

### Tour Booking
- Select tour date + participants
- Capacity enforcement using locking logic (per codebase review notes)
- Total price calculation

---

## 10) Admin Dashboard & Management

### Admin Dashboard
- `GET /admin/stats` returns analytics:
  - total revenue (succeeded payments)
  - booking counts
  - occupancy rate
  - revenue chart data by day
  - bookings by status
  - recent bookings

### Admin Management (CRUD)
- Admin endpoints are protected by admin/superadmin dependency checks.
- Admin UI supports:
  - Manage Hotels (CRUD + Cloudinary image upload/reorder/thumbnail)
  - Manage Rooms (CRUD)
  - Manage Tours (CRUD + images)
  - Manage Bookings (status update)
  - Manage Users (search/edit/delete)

### Latest UI behavior changes for admin/superadmin
- Superadmin sees all hotels/tours/rooms by not forcing `owner_id`.

---

## 11) Pricing UX Update (Hotel Price Removed from UI)

### Goal
When a user opens a hotel, they should choose a room to buy; therefore hotel-level pricing display should not be the primary price.

### Implemented behavior
- UI no longer shows `hotel.base_price` on hotel cards (Home/preview lists).
- Hotel preview price and hotel detail “starting price” are derived from room prices:
  - backend returns `min_room_price` for each hotel
  - frontend displays `min_room_price`

### Admin “Create Hotel” UI update
- Admin hotel creation no longer asks for a price field in the modal UI.

---

## 12) Search Calendar UI Update (Date Range)

### Requirement
- Select “from day” and “to day” in the search bar.
- Selected range should be highlighted (blue + bold).
- Month/year navigation should update the calendar table without closing.
- After selecting check-in/check-out, the calendar should remain open so the user can see the full date range.

### Implemented approach
- Replaced native `input type="date"` UI in the search bar with a custom date-range calendar component.
- Month and year are controlled via dropdowns in the popup header.
- The popup stays open after selecting check-out.

---

## 13) Testing Notes / Known Gaps (from existing review)
- Backend email sending is a placeholder (logging placeholder).
- Admin sorting and price filtering depend on pricing derivation logic.
- Some frontend ESLint issues exist unrelated to the latest date/calendar work (lint currently fails due to pre-existing unused imports).

