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
| `evt_` | Webhook event |
| `whsec_` | Webhook secret |
| `ck_test_` / `ck_live_` | API key |

## Customers

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/customers` | Create. Required: `name`. Optional: `email`, `phone` (E.164), `locale`, `taxId`, `metadata`. |
| GET | `/customers/:id` | Retrieve a single customer. |
| GET | `/customers` | List. Returns up to 100 most-recent customers; query parameters are not honoured. |
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
| POST | `/charges` | Create. Required: `customer`, `payment_method`, `amount` (positive integer, agorot). Optional: `currency` (default `ils`), `description`, `installments: { count }` (`count` integer min 1, default 1), `metadata`. |
| GET | `/charges/:id` | Retrieve a charge. |
| GET | `/charges` | List up to 100 most-recent. Optional `?customer=cus_*` filter (other query params are ignored). |

## Checkout Sessions (hosted payment page)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/checkout_sessions` | Create. Required: `customer` (`cus_*` — must already exist; no auto-create), `success_url`, `cancel_url`, and **exactly one** of `price` (single one-time or recurring price id) or `line_items` (ad-hoc cart). Optional: `create_document` (default true). sending both is rejected with 400 `invalid_request`. Returns `{ id, url, expires_at }`. TTL 30 minutes. |
| GET | `/checkout_sessions/:id/public` | Public, no auth. Used by the hosted page. |
| POST | `/checkout_sessions/:id/confirm` | Public. Submitted by the hosted page after the customer pays. |

`line_items` shape (when using the cart branch):

```json
[
  {
    "name": "Annual seat",
    "description": "Workspace seat for one year",
    "image_url": "https://example.com/seat.png",
    "amount_agorot": 49900,
    "quantity": 3
  }
]
```

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
| POST | `/subscriptions` | Create. Required: `customer`, `price` (must be recurring). Optional: `payment_method` (required for paid prices; may be omitted only when the price has `unit_amount === 0`), `metadata`. |
| GET | `/subscriptions/:id` | Retrieve. |
| GET | `/subscriptions` | List up to 100 most-recent. Query parameters are not honoured. |
| POST | `/subscriptions/:id/cancel` | Cancel. Optional body: `cancel_at_period_end` (boolean, default false). |
| GET | `/subscriptions/:id/public` | Customer-facing, uses callback token. |

Statuses: `active`, `canceled`, `incomplete`, `incomplete_expired`, `past_due`, `trialing`.

Lifecycle:
- `incomplete` -> `incomplete_expired` after 23 hours if first charge never succeeds.
- `active` -> `past_due` on a failed renewal. Retries at days 3, 7, 14. Then `canceled`.
- `subscription.trial_will_end` fires 3 days before `trial_end`.

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
