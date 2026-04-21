CREATE TABLE "loyalty_tier" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "name" varchar NOT NULL,
  "min_points" int NOT NULL DEFAULT 0,
  "max_points" int NOT NULL DEFAULT 0,
  "benefits" text,
  "discount_percent" decimal(5,2) DEFAULT 0
);

CREATE TABLE "users" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "full_name" varchar NOT NULL,
  "email" varchar UNIQUE NOT NULL,
  "password_hash" varchar NOT NULL,
  "phone_number" varchar NOT NULL,
  "role" varchar NOT NULL,
  "total_points" int DEFAULT 0,
  "loyalty_tier_id" uuid,
  "created_at" timestamp DEFAULT (now())
);

CREATE TABLE "hotel" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "admin_id" uuid NOT NULL,
  "liteapi_hotel_id" varchar,
  "name" varchar NOT NULL,
  "location" varchar,
  "star_rating" int,
  "description" text
);

CREATE TABLE "room" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "hotel_id" uuid NOT NULL,
  "liteapi_room_id" varchar,
  "title" varchar NOT NULL,
  "description" text,
  "price_per_night" decimal(10,2) NOT NULL,
  "max_guests" int DEFAULT 1,
  "amenities" text
);

CREATE TABLE "room_image" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "room_id" uuid NOT NULL,
  "image_url" varchar NOT NULL
);

CREATE TABLE "room_availability" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "room_id" uuid NOT NULL,
  "date" date NOT NULL,
  "status" varchar NOT NULL DEFAULT 'available'
);

CREATE TABLE "tour" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "admin_id" uuid NOT NULL,
  "viator_product_code" varchar,
  "title" varchar NOT NULL,
  "description" text,
  "location" varchar,
  "price" decimal(10,2) NOT NULL
);

CREATE TABLE "tour_image" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "tour_id" uuid NOT NULL,
  "image_url" varchar NOT NULL
);

CREATE TABLE "tour_schedule" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "tour_id" uuid NOT NULL,
  "available_date" date NOT NULL,
  "total_slots" int NOT NULL DEFAULT 0,
  "booked_slots" int NOT NULL DEFAULT 0
);

CREATE TABLE "flight_booking" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "duffel_order_id" varchar UNIQUE NOT NULL,
  "duffel_booking_ref" varchar,
  "airline_name" varchar NOT NULL,
  "flight_number" varchar NOT NULL,
  "departure_airport" varchar NOT NULL,
  "arrival_airport" varchar NOT NULL,
  "departure_at" timestamp NOT NULL,
  "arrival_at" timestamp NOT NULL,
  "cabin_class" varchar,
  "passenger_name" varchar NOT NULL,
  "passenger_email" varchar NOT NULL,
  "base_amount" decimal(10,2) NOT NULL,
  "total_amount" decimal(10,2) NOT NULL,
  "currency" varchar DEFAULT 'VND',
  "status" varchar DEFAULT 'confirmed',
  "created_at" timestamp DEFAULT (now())
);

CREATE TABLE "voucher" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "admin_id" uuid NOT NULL,
  "code" varchar UNIQUE NOT NULL,
  "name" varchar NOT NULL,
  "discount_type" varchar NOT NULL,
  "discount_value" decimal(10,2) NOT NULL,
  "min_order_value" decimal(10,2) DEFAULT 0,
  "max_uses" int DEFAULT 1,
  "used_count" int DEFAULT 0,
  "valid_from" date NOT NULL,
  "valid_to" date NOT NULL,
  "status" varchar DEFAULT 'active'
);

CREATE TABLE "booking" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "user_id" uuid NOT NULL,
  "voucher_id" uuid,
  "total_price" decimal(10,2) NOT NULL,
  "discount_amount" decimal(10,2) DEFAULT 0,
  "points_earned" int DEFAULT 0,
  "points_redeemed" int DEFAULT 0,
  "status" varchar DEFAULT 'pending',
  "created_at" timestamp DEFAULT (now())
);

CREATE TABLE "booking_item" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "booking_id" uuid NOT NULL,
  "item_type" varchar NOT NULL,
  "room_id" uuid,
  "check_in" date,
  "check_out" date,
  "tour_schedule_id" uuid,
  "flight_booking_id" uuid,
  "unit_price" decimal(10,2) NOT NULL,
  "subtotal" decimal(10,2) NOT NULL,
  "quantity" int DEFAULT 1,
  "status" varchar DEFAULT 'pending'
);

CREATE TABLE "payment" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "booking_id" uuid NOT NULL,
  "amount" decimal(10,2) NOT NULL,
  "currency" varchar DEFAULT 'VND',
  "payment_method" varchar,
  "provider" varchar NOT NULL,
  "provider_transaction_id" varchar,
  "status" varchar DEFAULT 'pending',
  "created_at" timestamp DEFAULT (now())
);

CREATE TABLE "voucher_usage" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "voucher_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "booking_id" uuid NOT NULL,
  "used_at" timestamp DEFAULT (now())
);

CREATE TABLE "loyalty_transaction" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "user_id" uuid NOT NULL,
  "booking_id" uuid,
  "points" int NOT NULL,
  "type" varchar NOT NULL,
  "description" varchar,
  "created_at" timestamp DEFAULT (now())
);

CREATE TABLE "review" (
  "id" uuid PRIMARY KEY DEFAULT (gen_random_uuid()),
  "user_id" uuid NOT NULL,
  "hotel_id" uuid,
  "tour_id" uuid,
  "booking_item_id" uuid,
  "rating" int NOT NULL,
  "comment" text,
  "created_at" timestamp DEFAULT (now())
);

CREATE UNIQUE INDEX "uq_room_date" ON "room_availability" ("room_id", "date");

CREATE UNIQUE INDEX "uq_tour_date" ON "tour_schedule" ("tour_id", "available_date");

CREATE UNIQUE INDEX "uq_voucher_user" ON "voucher_usage" ("voucher_id", "user_id");

COMMENT ON COLUMN "loyalty_tier"."name" IS 'e.g. Bronze, Silver, Gold, Platinum';

COMMENT ON COLUMN "users"."role" IS 'customer | admin';

COMMENT ON COLUMN "hotel"."liteapi_hotel_id" IS 'hotel ID from LiteAPI — used for rates & booking calls';

COMMENT ON COLUMN "room"."liteapi_room_id" IS 'room ID from LiteAPI — used for roomMapping';

COMMENT ON COLUMN "room_availability"."status" IS 'available | booked | blocked';

COMMENT ON COLUMN "tour"."viator_product_code" IS 'productCode from Viator API — used for availability & booking';

COMMENT ON COLUMN "flight_booking"."duffel_order_id" IS 'order ID returned by Duffel POST /air/orders';

COMMENT ON COLUMN "flight_booking"."duffel_booking_ref" IS 'human-readable booking reference, e.g. XYZ123';

COMMENT ON COLUMN "flight_booking"."departure_airport" IS 'IATA code, e.g. SGN';

COMMENT ON COLUMN "flight_booking"."arrival_airport" IS 'IATA code, e.g. HAN';

COMMENT ON COLUMN "flight_booking"."cabin_class" IS 'economy | business | first';

COMMENT ON COLUMN "flight_booking"."status" IS 'confirmed | cancelled | refunded';

COMMENT ON COLUMN "voucher"."discount_type" IS 'percentage | fixed';

COMMENT ON COLUMN "voucher"."status" IS 'active | expired | disabled';

COMMENT ON COLUMN "booking"."voucher_id" IS 'nullable — applied at order level';

COMMENT ON COLUMN "booking"."total_price" IS 'sum of all item subtotals';

COMMENT ON COLUMN "booking"."status" IS 'pending | confirmed | cancelled | completed';

COMMENT ON COLUMN "booking_item"."item_type" IS 'room | tour | flight';

COMMENT ON COLUMN "booking_item"."room_id" IS 'nullable — used when item_type = room';

COMMENT ON COLUMN "booking_item"."check_in" IS 'room: check-in date';

COMMENT ON COLUMN "booking_item"."check_out" IS 'room: check-out date';

COMMENT ON COLUMN "booking_item"."tour_schedule_id" IS 'nullable — used when item_type = tour';

COMMENT ON COLUMN "booking_item"."flight_booking_id" IS 'nullable — used when item_type = flight';

COMMENT ON COLUMN "booking_item"."unit_price" IS 'price per night / ticket / seat at booking time';

COMMENT ON COLUMN "booking_item"."status" IS 'pending | confirmed | cancelled';

COMMENT ON COLUMN "payment"."payment_method" IS 'credit_card | bank_transfer | e_wallet | atm_card';

COMMENT ON COLUMN "payment"."provider" IS 'stripe | vnpay';

COMMENT ON COLUMN "payment"."provider_transaction_id" IS 'Stripe: payment_intent_id | VNPay: vnp_TransactionNo';

COMMENT ON COLUMN "payment"."status" IS 'pending | success | failed | refunded';

COMMENT ON COLUMN "loyalty_transaction"."points" IS 'positive = earned, negative = redeemed';

COMMENT ON COLUMN "loyalty_transaction"."type" IS 'earn | redeem | adjust';

COMMENT ON COLUMN "review"."hotel_id" IS 'nullable — set when item_type = room';

COMMENT ON COLUMN "review"."tour_id" IS 'nullable — set when item_type = tour';

COMMENT ON COLUMN "review"."booking_item_id" IS 'ensures only verified customers can review';

COMMENT ON COLUMN "review"."rating" IS '1 to 5';

ALTER TABLE "users" ADD FOREIGN KEY ("loyalty_tier_id") REFERENCES "loyalty_tier" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "hotel" ADD FOREIGN KEY ("admin_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "room" ADD FOREIGN KEY ("hotel_id") REFERENCES "hotel" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "room_image" ADD FOREIGN KEY ("room_id") REFERENCES "room" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "room_availability" ADD FOREIGN KEY ("room_id") REFERENCES "room" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tour" ADD FOREIGN KEY ("admin_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tour_image" ADD FOREIGN KEY ("tour_id") REFERENCES "tour" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "tour_schedule" ADD FOREIGN KEY ("tour_id") REFERENCES "tour" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "voucher" ADD FOREIGN KEY ("admin_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "booking" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "booking" ADD FOREIGN KEY ("voucher_id") REFERENCES "voucher" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "booking_item" ADD FOREIGN KEY ("booking_id") REFERENCES "booking" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "booking_item" ADD FOREIGN KEY ("room_id") REFERENCES "room" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "booking_item" ADD FOREIGN KEY ("tour_schedule_id") REFERENCES "tour_schedule" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "booking_item" ADD FOREIGN KEY ("flight_booking_id") REFERENCES "flight_booking" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "payment" ADD FOREIGN KEY ("booking_id") REFERENCES "booking" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "voucher_usage" ADD FOREIGN KEY ("voucher_id") REFERENCES "voucher" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "voucher_usage" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "voucher_usage" ADD FOREIGN KEY ("booking_id") REFERENCES "booking" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "loyalty_transaction" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "loyalty_transaction" ADD FOREIGN KEY ("booking_id") REFERENCES "booking" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "review" ADD FOREIGN KEY ("user_id") REFERENCES "users" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "review" ADD FOREIGN KEY ("hotel_id") REFERENCES "hotel" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "review" ADD FOREIGN KEY ("tour_id") REFERENCES "tour" ("id") DEFERRABLE INITIALLY IMMEDIATE;

ALTER TABLE "review" ADD FOREIGN KEY ("booking_item_id") REFERENCES "booking_item" ("id") DEFERRABLE INITIALLY IMMEDIATE;
