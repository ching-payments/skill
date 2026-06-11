# CHING Public API Endpoint Reference

Base URL: `https://api.ching.co.il/ching/v1`
Auth: `Authorization: Bearer ck_test_<64hex>` or `Authorization: Bearer ck_live_<64hex>`
Content type: `application/json`
Mode toggle: send `X-Livemode: false` to force test mode (live keys default to live).

## ID Prefixes

| Prefix | Resource |
|--------|----------|
| `proj_` | Project |
| `cus_` | Customer |
| `pm_` | Payment method |
| `ch_` | Charge |
| `re_` | Refund |
| `co_` | Checkout session |
| `seti_` | Setup session |
| `prod_` | Product |
| `price_` | Price |
| `sub_` | Subscription |
| `si_` | Subscription item |
| `disc_` | Discount rule (coupon) |
| `di_` | Applied discount (rule bound to a subscription) |
| `evt_` | Webhook event |
| `whsec_` | Webhook secret |
| `ck_test_` / `ck_live_` | API key |

## Customers

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/customers` | Create. Required: `name`. Optional: `email`, `phone` (E.164), `locale`, `taxId`, `metadata`. Fires `customer.created`. |
| POST | `/customers/:id` | Update. All fields optional. Fires `customer.updated`. |
| POST | `/customers/upsert` | Create-or-update by `identifyBy` (`email` / `taxId` / `phone`). Patches the most-recent match in the current mode, else creates. Response carries `action: "created" | "updated"`; `name` required only on create. Fires `customer.created` or `customer.updated`. |
| GET | `/customers/:id` | Retrieve a single customer. |
| GET | `/customers` | List. Returns up to 100 most-recent customers; query parameters are not honoured. Soft-deleted customers are excluded. |
| DELETE | `/customers/:id` | Soft-delete (tombstone). Charges/documents/subscriptions keep referencing it; saved cards are detached. Returns `409 CUSTOMER_HAS_ACTIVE_SUBSCRIPTION` if a subscription is `active`/`trialing`/`past_due` (cancel it first). Idempotent. Fires `customer.deleted`. |
| GET | `/customers/:id/payment_methods` | List active saved cards on the customer. |
| GET | `/customers/:id/payment_methods/inactive` | List detached cards (history). |

## Payment Methods

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/payment_methods/:id` | Retrieve a saved card. |
| POST | `/payment_methods/:id/detach` | Remove a saved card. No body. |
| POST | `/payment_methods/test-card` | Sandbox only (test mode). Mints a synthetic saved card. Required: `customer`. Optional: `card_index` (integer 0-2; 0 = visa, 1 = mastercard, 2 = amex; default 0). |

There is **no** top-level `GET /payment_methods` listing across the project; query saved cards via `GET /customers/:id/payment_methods` instead.

## Charges (one-time payments)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/charges` | Create. Required: `customer`, `payment_method`, `amount` (positive integer, agorot). Optional: `currency` (default `ils`), `description`, `installments: { count }` (`count` integer min 1, default 1), `metadata`. Always automatic capture - the saved-card API does not accept `capture_method=manual` (use checkout sessions for that). |
| GET | `/charges/:id` | Retrieve a charge. Response includes `capture_method`, `authorized_at`, `capturable_until`, `captured_at`, `amount_captured`, `cancellation_reason` for J4J5 manual-capture charges. |
| GET | `/charges` | List up to 100 most-recent. Optional `?customer=cus_*` filter (other query params are ignored). |
| POST | `/charges/:id/capture` | Capture a manual-capture charge currently in `requires_capture`. Optional body: `amount` (integer agorot, partial capture - must be ≤ original authorized amount; difference auto-released to customer). Fires `charge.captured`, issues the tax document, emails the receipt. Errors: `charge_not_capturable`, `capture_amount_too_large`, `charge_authorization_expired`, `provider_error`. |
| POST | `/charges/:id/cancel` | Cancel (void) a manual-capture charge in `requires_capture`. Optional body: `cancellation_reason` (`requested_by_customer` / `fraudulent` / `abandoned`; default `requested_by_customer`). Fires `charge.canceled`. CHING-side release is immediate; customer's bank may take up to 10 days to release the hold. Errors: `charge_not_cancelable`. For captured charges use `POST /refunds` instead. |

Charge statuses: `pending`, `processing`, `succeeded`, `failed`, `canceled`, `requires_capture` (new - manual-capture authorization awaiting capture/cancel).

Charge `capture_method`: `automatic` (default; J4 - charge immediately) or `manual` (J5 - authorize then capture). Manual capture is only enabled via the checkout sessions API; the daily sweep auto-cancels held charges at `capturable_until` (~7 days after authorization).

## Checkout Sessions (hosted payment page)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/checkout_sessions` | Create. Required: `customer` (`cus_*` - must already exist; no auto-create), `success_url`, `cancel_url`, and a mode selector: `price` alone (single one-time or recurring price id), `line_items` alone (ad-hoc cart), or **both `price` and `line_items`** (mixed: recurring plan + one-time items; the `price` must be recurring or it is rejected with `mixed_requires_recurring_price`). There is no `mode` field; the keys you send pick the mode. Optional: `create_document` (default true), `capture_method` (`automatic` default; or `manual` for J4J5 authorize-then-capture - only valid for one-time prices or carts with a new card; rejected for recurring prices and for mixed), `coupon_codes` (array of code strings, max 20, each ≤64 chars - pre-applied to the session so the hosted page shows them already attached as removable chips). Returns `{ id, url, expires_at }`. TTL 30 minutes. Every supplied `coupon_codes` entry is validated up front: an unknown code is rejected with `400 discount_code_not_found` (runtime states like expired/exhausted/no-matching-target are not errors - they simply produce no chip). |
| GET | `/checkout_sessions/:id/public` | Public, no auth. Used by the hosted page. Includes a read-only discount preview: `discounts` (the rules currently reducing this session: `[{ id, code, name }]` - automatic matches plus any persisted code), `discount_lines` (`[{ name, amount_agorot }]`), `total_discount_agorot`, and `plan_discount_agorot` (the portion landing on a recurring plan line; 0 when there is no plan line). |
| POST | `/checkout_sessions/:id/discount` | Public. Apply a coupon code to a pending session: body `{ code }`. A code may map to several rules (one coupon, different effects per product/price); every gate-passing rule that actually reduces a line is linked. Returns the recomputed discount summary (`{ discounts, discount_lines, total_discount_agorot, plan_discount_agorot }`). Errors: `invalid_code` (404, no rule under the code), `session_not_pending` (409), `expired` / `exhausted` / `inactive` (all rules gated out), `not_applicable` (400, gate-passing but nothing in the cart matched - currency mismatch or target absent). Idempotent. |
| DELETE | `/checkout_sessions/:id/discount/:code` | Public. Remove a previously-applied code from the session (unlinks every rule the code maps to). Returns the recomputed discount summary. |
| POST | `/checkout_sessions/:id/confirm` | Public. Submitted by the hosted page after the customer pays. |

`line_items` shape (same for the cart branch and the mixed branch):

```json
[
  {
    "name": "Annual seat",
    "description": "Workspace seat for one year",
    "image_url": "https://example.com/seat.png",
    "amount_agorot": 49900,
    "quantity": 3,
    "price": "price_annualSeat"
  }
]
```

`price` and `product` are optional. A line item is ad-hoc by default and has no link to a CHING product/price, so product/price-targeted discounts do **not** apply to it (only order-level discounts do). Set `price` (the CHING price id; also resolves its parent product) or `product` to make the line eligible for product/price-targeted discounts; an unknown id returns `400 line_item_target_not_found`. Required when you sell CHING-catalog items you want to discount; not needed for pure e-commerce SKUs that aren't CHING products.

## Setup Sessions (save card without charging)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/setup_sessions` | Create. Required: `customer`, `success_url`, `cancel_url`. Optional: `metadata`. Returns `{ id, url, expires_at }`. TTL 24 hours. |
| GET | `/setup_sessions/:id` | Merchant-authenticated retrieve. |
| POST | `/setup_sessions/:id/cancel` | Cancel a pending setup session. No body. |
| GET | `/setup_sessions/:id/public` | Public, no auth. Used by the hosted page. |

Statuses: `pending`, `requires_action`, `succeeded`, `canceled`, `failed`, `expired`.

## Subscriptions (recurring billing)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/subscriptions` | Create. Required: `customer`, `price` (must be recurring). Optional: `payment_method` (required for paid prices; may be omitted only when the price has `unit_amount === 0`), `discounts` (array of `{ code }` or `{ discount: "disc_*" }` entries to attach; automatic product/price rules targeting this price attach on their own too), `metadata`. Each attached rule becomes an `applied_discount` (`di_*`) that reduces the first and renewal charges for its `duration`. |
| GET | `/subscriptions/:id` | Retrieve (expanded `items`). Also returns a next-charge estimate: `next_charge_subtotal` (gross before discounts), `next_charge_discount_amount`, `next_charge_amount` (charged amount = subtotal - discount), all agorot, plus `next_charge_discounts` (one entry per discount reducing that charge: `name`, `value_type`, `value`, `duration`, `amount_off`, and `charges_remaining` for `n_charges` / `ends_at` for `until_date`, both null otherwise). Empty/absent when no discount applies. GET-only - not on list or create. |
| GET | `/subscriptions` | List up to 100 most-recent (each row carries `customer_name`; `items` empty and the `next_charge_*` estimate omitted - fetch the single subscription for those). Query parameters are not honoured. |
| POST | `/subscriptions/:id/cancel` | Cancel. Optional body: `cancel_at_period_end` (boolean, default false). |
| GET | `/subscriptions/:id/public` | Customer-facing, uses callback token. |

Statuses: `active`, `canceled`, `incomplete`, `incomplete_expired`, `past_due`, `trialing`.

Lifecycle:
- `incomplete` -> `incomplete_expired` after 23 hours if first charge never succeeds.
- `active` -> `past_due` on a failed renewal. Retries at days 3, 7, 14. Then `canceled`.
- `subscription.trial_will_end` fires 3 days before `trial_end`.

## Discounts & Coupons

A **discount rule** (`disc_*`) reduces what a customer pays. It is either **automatic** (applies on its own whenever a matching product/price/order is bought) or a **code** (the customer types it at checkout). Rules can target the whole `order`, specific `products`, or specific `prices`. When a rule is attached to a subscription it becomes an **applied discount** (`di_*`) that reduces charges for its `duration`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/discounts` | Create a rule. See body fields below. Fires `discount.created`. |
| GET | `/discounts` | List up to 100 most-recent rules. |
| GET | `/discounts/:id` | Retrieve a rule (includes its resolved `targets`). |
| POST | `/discounts/:id` | Update **mutable** fields only: `name`, `active`, `active_from`, `active_until`, `max_redemptions`, `max_redemptions_per_customer`, `metadata`. Value/type/target_type/duration are frozen once the rule exists so already-applied discounts keep their terms. Fires `discount.updated`. |
| POST | `/discounts/:id/targets` | Replace the full set of product/price targets: body `{ targets: [visibleId, ...] }`. Ids must match the rule's `target_type` (`products` → `prod_*`, `prices` → `price_*`). Rejected for `order` rules with `targets_not_supported`. Fires `discount.updated`. |
| POST | `/discounts/:id/archive` | Soft-delete (archive) a rule. An archived rule never matches at checkout/renewal, but already-attached applied-discounts run out their own duration. Idempotent. Fires `discount.deleted`. |
| GET | `/discounts/:id/redemptions` | Read-only detail: `{ redemptions: [...], applied_discounts: [...] }`. Each redemption carries `customer`, `customer_name`, `customer_email`, `subscription`, `charge`, `charge_amount`, `currency`, `amount_saved`, `created` (free-plan/trial redemptions carry null charge/amount). Each applied-discount carries `subscription`, `status`, `charges_applied`, `duration_charges`, `started_at`, `ends_at`. |

`POST /discounts` body fields:

| Field | Required | Notes |
|-------|----------|-------|
| `name` | yes | 1-255 chars. |
| `redemption` | yes | `automatic` or `code`. |
| `code` | when `redemption=code` | Normalized to UPPERCASE; charset `[A-Z0-9_-]{1,64}`. **Not unique** - several rules may share one coupon code to reduce different products/prices differently. Must be omitted for `automatic` rules. |
| `target_type` | yes | `order` (whole order/cart, apportioned across lines), `products`, or `prices`. |
| `targets` | when `products`/`prices` | Array of product or price visibleIds the rule reduces. Unknown id → `400 target_not_found`. |
| `value_type` | yes | `percent` (`value` = basis points, 2500 = 25%, max 10000), `amount` (`value` = agorot to subtract), or `override` (`value` = agorot target unit price). |
| `value` | yes | Integer ≥ 0. |
| `value_tax_mode` | `override` only | `inclusive` (default) or `exclusive` - whether the override price is quoted incl. or excl. VAT. |
| `currency` | for `amount`/`override` | e.g. `ils`. Must be omitted for `percent`. |
| `duration` | yes | `once`, `n_charges`, `until_date`, or `forever` - how long the rule keeps reducing once attached to a subscription. |
| `duration_charges` | when `n_charges` | Positive integer. |
| `duration_until` | when `until_date` | ISO 8601 datetime. |
| `active_from` / `active_until` | no | ISO 8601 window the rule is eligible. |
| `max_redemptions` / `max_redemptions_per_customer` | no | Positive integer caps. |
| `active` | no | Boolean, default true. |
| `metadata` | no | Object. |

Discount object (`object: "discount"`): `id`, `name`, `redemption`, `code`, `target_type`, `targets` (resolved visibleIds), `value_type`, `value`, `value_tax_mode`, `currency`, `duration`, `duration_charges`, `duration_until`, `active_from`, `active_until`, `max_redemptions`, `max_redemptions_per_customer`, `times_redeemed`, `active`, `archived`, `metadata`, `livemode`, `created`.

Applied-discount status (`di_*`): `active` (still reducing charges), `completed` (its duration ran out), `canceled` (the subscription ended or the merchant detached it).

To use a code at checkout, send it via `coupon_codes` on `POST /checkout_sessions`, or apply it on the hosted page via `POST /checkout_sessions/:id/discount`. To attach a rule to a subscription created over the API, pass `discounts` on `POST /subscriptions`.

## Refunds

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/refunds` | Required: `charge`, `amount` (positive integer, agorot). Optional: `reason` (`requested_by_customer` / `duplicate` / `fraudulent`), `metadata`. There is no "defaults to remaining" - the caller must supply the exact amount. |
| GET | `/refunds/:id` | Retrieve. |
| GET | `/refunds` | List. |

Statuses: `pending`, `succeeded`, `failed`.

## Products

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/products` | Create. Required: `name`. Optional: `description`, `image_url` (must be a URL), `features` (array of `{ title, subtitle? }`), `unlisted` (bool; rejected when sent via API key — dashboard only), `metadata`. |
| POST | `/products/:id` | Update. All fields optional: `name`, `description` (nullable), `image_url` (nullable URL), `features` (nullable array), `active` (bool), `unlisted` (bool), `metadata`. |
| POST | `/products/upload_image` | Upload an image and get back a URL to use as `image_url`. Required: `content` (base64, no `data:` prefix, max ~2MB). Optional: `content_type` (`image/png` / `image/jpeg` / `image/webp` / `image/gif`; default `image/png`), `filename` (without extension). |
| GET | `/products/:id` | Retrieve. |
| GET | `/products` | List. |

## Prices

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/prices` | Create. Required: `product`, `unit_amount` (non-negative integer in agorot — 0 is allowed for free plans), `type` (`one_time` or `recurring`). For recurring: nested `recurring: { interval: "month" \| "year", interval_count?: integer >= 1 (default 1), trial_period_days?: integer >= 0 }`. Optional top-level: `currency` (default `ils`), `tax_mode` (`inclusive` or `exclusive`; default `inclusive`), `metadata`. There is no top-level `name`, `active`, or `trial_period_days` on create. |
| POST | `/prices/:id` | Update (strict — unknown fields rejected). Required: `apply_mode` (`now` / `new_subscribers_only` / `scheduled`). Optional: `unit_amount`, `trial_period_days` (nullable), `tax_mode`, `effective_date` (ISO 8601 datetime; required when `apply_mode === "scheduled"`), `metadata`. |
| DELETE | `/prices/:id/pending_migration` | Cancel a previously-scheduled price change before it takes effect. No body. |
| GET | `/prices/:id` | Retrieve. |
| GET | `/prices` | List. Optional `?product=prod_*` filter and `?active=true|false|all` (default returns active only). |

## Webhook endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/webhooks` | Required: `url` (any valid URL — HTTPS strongly recommended but not enforced by the schema), `events` (non-empty array of event-type strings, or `["*"]`). Returns the `whsec_*` secret **once**. Store it immediately. |
| GET | `/webhooks` | List configured endpoints. |
| DELETE | `/webhooks/:id` | Remove an endpoint. |

## Billing Portal

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/billing_portal_sessions` | Required: `customer`. Optional: `return_url` (must be a URL). Returns `{ url, expires_at }`. TTL 30 minutes. |

## Documents (invoices)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/documents` | List up to 100 most-recent documents on the project. Query parameters are not honoured. |
| GET | `/documents/:id` | Retrieve metadata. |
| GET | `/documents/:id/pdf` | Download PDF binary. |

Document types align with Israeli tax requirements: `tax_invoice_receipt`, `receipt`, etc. Issued automatically when a charge succeeds (controlled by `create_document` on Checkout sessions).

## Error response shape

All errors return HTTP 4xx/5xx with body:

```json
{
  "success": false,
  "error": {
    "status": 400,
    "code": "INVALID_FIELD",
    "message": "Human-readable message (may be Hebrew)",
    "issues": [
      { "path": "amount", "message": "must be a positive integer" }
    ]
  }
}
```

Common codes: `WRONG_CREDENTIALS` (401), `NO_ACCESS` (403), `LIVE_KEY_INACTIVE` (403), `NOT_FOUND` (404), `INVALID_FIELD` (422), `EMAIL_EXISTS` (409), `PROJECT_NOT_FOUND` (404).

## Conventions

- All amount fields are integers in **agorot** (1 ILS = 100 agorot). Never send floats.
- All timestamps are ISO 8601 UTC strings.
- List responses are `{ success: true, data: [...] }` — there is no `object: "list"` envelope and no `has_more` flag.
- List endpoints currently return up to 100 most-recent rows; there is no `limit` or `starting_after` pagination yet. Server-side filtering is supported only on `GET /charges?customer=...` and `GET /prices?product=...&active=...`.
- No idempotency keys. Implement client-side dedupe for writes.
