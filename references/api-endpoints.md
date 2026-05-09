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
| GET | `/customers` | List. Pagination via `limit`. |
| GET | `/customers/:id/payment_methods` | List active saved cards on the customer. |
| GET | `/customers/:id/payment_methods/inactive` | List detached cards (history). |

## Payment Methods

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/payment_methods/:id` | Retrieve a saved card. |
| GET | `/payment_methods` | List all payment methods on the project. |
| POST | `/payment_methods/:id/detach` | Remove a saved card. |
| POST | `/payment_methods/test_card` | Sandbox only. Mints a test card. Required: `customer`. Optional: `brand`, `last4`, `exp_month`, `exp_year`. |

## Charges (one-time payments)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/charges` | Create. Required: `customer`, `payment_method`, `amount` (agorot). Optional: `currency` (default `ils`), `description`, `installments: { count }`, `metadata`. |
| GET | `/charges/:id` | Retrieve a charge. |
| GET | `/charges` | List, paginated. Filter by `customer`. |

## Checkout Sessions (hosted payment page)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/checkout_sessions` | Create. Required: `mode` (`single_price` or `cart`), `success_url`, `cancel_url`. Either `price` (single_price) or `line_items` (cart). Optional: `customer`, `create_document` (default true), `metadata`. Returns `{ id, url, expires_at }`. TTL 30 minutes. |
| GET | `/checkout_sessions/:id/public` | Public, no auth. Used by the hosted page. |
| POST | `/checkout_sessions/:id/confirm` | Public. Submitted by the hosted page after the customer pays. |

`line_items` shape (for `mode: "cart"`):

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
| GET | `/setup_sessions/:id/public` | Public, no auth. Used by the hosted page. |

Statuses: `pending`, `requires_action`, `succeeded`, `canceled`, `failed`, `expired`.

## Subscriptions (recurring billing)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/subscriptions` | Create. Required: `customer`, `price` (must be recurring). Optional: `payment_method` (required after trial), `metadata`. |
| GET | `/subscriptions/:id` | Retrieve. |
| GET | `/subscriptions` | List. Filter by `customer`, `status`. |
| POST | `/subscriptions/:id/cancel` | Cancel. |
| GET | `/subscriptions/:id/public` | Customer-facing, uses callback token. |

Statuses: `active`, `canceled`, `incomplete`, `incomplete_expired`, `past_due`, `trialing`.

Lifecycle:
- `incomplete` -> `incomplete_expired` after 23 hours if first charge never succeeds.
- `active` -> `past_due` on a failed renewal. Retries at days 3, 7, 14. Then `canceled`.
- `subscription.trial_will_end` fires 3 days before `trial_end`.

## Refunds

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/refunds` | Required: `charge`. Optional: `amount_agorot` (defaults to remaining), `reason` (`requested_by_customer` / `duplicate` / `fraudulent`), `metadata`. |
| GET | `/refunds/:id` | Retrieve. |
| GET | `/refunds` | List. |

Statuses: `pending`, `succeeded`, `failed`.

## Products

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/products` | Required: `name`. Optional: `description`, `image_url`, `features` (array), `unlisted` (bool), `metadata`. |
| GET | `/products/:id` | Retrieve. |
| GET | `/products` | List. |

## Prices

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/prices` | Required: `product`, `amount_agorot`, `type` (`one_time` or `recurring`). For recurring: `recurring: { interval: "day"\|"week"\|"month"\|"year", count?: 1 }`. Optional: `currency` (default `ils`), `tax_mode` (`inclusive` or `exclusive`), `trial_period_days`, `name`, `active` (default true), `metadata`. |
| GET | `/prices/:id` | Retrieve. |
| GET | `/prices` | List. Filter by `product`. |

## Webhook endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/webhooks` | Required: `url` (HTTPS), `events` (array of types or `["*"]`). Returns the `whsec_*` secret **once**. Store it immediately. |
| GET | `/webhooks` | List configured endpoints. |
| DELETE | `/webhooks/:id` | Remove an endpoint. |

## Billing Portal

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/billing_portal_sessions` | Required: `customer`. Optional: `return_url`. Returns `{ url, expires_at }`. TTL ~1 hour. |

## Documents (invoices)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/documents` | List. Filter by `customer`, `type`. |
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
- All list responses follow `{ object: "list", data: [...], has_more: bool }`.
- Pagination via `limit` (default 20, max 100) and `starting_after: <id>`.
- No idempotency keys. Implement client-side dedupe for writes.
