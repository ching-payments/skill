---
name: ching-payments-integration
description: >-
  Integrate the CHING payments API into a SaaS or web product to accept
  Israeli card payments, save cards, run subscriptions, issue refunds,
  and host a customer billing portal. Use when the user asks to
  "integrate CHING", "add CHING checkout", "accept payments in Israel",
  "lekabel tashlumim", "lehosif tashlum", "leshalev CHING", set up
  webhooks for charge.succeeded, build a hosted billing flow for
  ILS, or use the @ching-payments/cli to scaffold products and prices.
  Covers ck_test_/ck_live_ keys, agorot amounts, HMAC webhook
  verification, and the redirect-only checkout/setup flow at
  secured.ching.co.il. Do NOT use for non-Israeli payment processors
  or for Glance accounting/invoicing flows unrelated to CHING payments.
license: MIT
allowed-tools: 'Bash(npx:*) Bash(python3:*) WebFetch'
---

# CHING Payments Integration

CHING is an Israeli payments platform with a modern REST API and hosted checkout, setup, and billing-portal pages. This skill walks you through integrating CHING into a SaaS or web product end-to-end: scaffold the catalog with the CLI, take a one-time payment with Checkout, save a card with Setup, run subscriptions, verify webhooks, and ship the billing portal.

## Mental Model

Read this once, then refer back as needed.

| Concept | What it is in CHING |
|---------|---------------------|
| Project | A live merchant account; holds keys and config |
| API key | `ck_test_<64hex>` or `ck_live_<64hex>` (sent as `Authorization: Bearer <key>`) |
| Product | A thing you sell ("Pro plan", "1 hour consult") |
| Price | An amount in agorot tied to a product, one_time or recurring |
| Customer | The end-payer (cus_*) |
| Payment Method | A saved card on a customer (pm_*) |
| Checkout Session | Hosted page for a single charge or cart (co_*) |
| Setup Session | Hosted page that saves a card without charging (seti_*) |
| Subscription | Recurring billing using a saved card (sub_*) |
| Charge | A single payment attempt (ch_*) |
| Refund | A partial or full reversal (re_*) |
| Billing Portal | Hosted self-service page for the customer |
| Webhook | Signed HTTPS POST to your endpoint when an event happens |

**Three golden rules** that prevent most integration bugs:

1. **Amounts are always in agorot, never in shekels.** ₪49.90 is `4990`. Multiplying by 100 at the API boundary, dividing by 100 at the UI boundary.
2. **Checkout and Setup are redirect-only.** You create a session server-side, redirect the customer to the returned `url`, and find out the result via webhook. The `success_url` is for UX only, never trust query params from it for fulfillment.
3. **Create the customer once, then persist its `cus_*` id on your own user record and reuse it for every action on that person's behalf** - checkout sessions, setup sessions, subscriptions, charges, and billing-portal sessions. The `cus_*` id is the durable handle that ties everything together: saved cards, subscriptions (and therefore the user's current plan), charge history, and tax documents all hang off it. Reuse it and the user's plan and their self-service billing-portal pages persist across sessions; create a fresh customer each time and you fragment that person into disconnected records - duplicate customers, a card saved on one but billed on another, a "missing" subscription, and a portal that shows nothing. One person in your system = one CHING customer, forever.

## Instructions

### Step 1: Sign up and configure the merchant dashboard

Have the user open https://app.ching.co.il and:

1. Register the project (email + password or Google OAuth). Provide business name, tax ID (`misparHaP`), and business type (`COMPANY`, `MURSHE`, `PATOOR`).
2. Stay in test mode (top bar toggle) for development.
3. Settings to API Keys (`/api-keys`), create a key. The full value is shown **once**, copy it immediately. Format: `ck_test_<64 hex chars>`.
4. Settings to Webhooks (`/webhooks`), add the merchant's HTTPS endpoint and select event types (or `["*"]`). Copy the `whsec_<hex>` secret **once**, store as `CHING_WEBHOOK_SECRET`.

Steps 3 and 4 can also be done from the terminal with the CLI - `ching api-keys create` and `ching webhooks create` both print the secret once, just like the dashboard. See Step 2.

To go live later, the merchant must complete:
- Payment provider activation (Grow KYC iframe at `/settings` -> "Join Grow")
- Linked business identity (taxId + company name + type)
- Then the dashboard unlocks `ck_live_*` key creation

Tell the user to put the key + secret in their server env, never client-side:

```
CHING_API_KEY=ck_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHING_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHING_API_BASE=https://api.ching.co.il
```

### Step 2: Bootstrap products and prices with the CLI

The CLI is the fastest way to seed catalog data. Install on demand with `npx`, no global install required.

```bash
# Authenticate (opens browser)
npx @ching-payments/cli login

# Or paste an API key (CI / non-interactive)
npx @ching-payments/cli login --with-key

# Confirm
npx @ching-payments/cli whoami
```

Optional, manage projects from the terminal (handy for spinning up a separate staging project):

```bash
# List every project on your account; the active one is marked
npx @ching-payments/cli projects list

# Create a new project. With no active project, the new one is auto-adopted
npx @ching-payments/cli projects create --name "Acme Staging"

# Force-switch to a freshly created project
npx @ching-payments/cli projects create --name "Acme EU" --switch
```

The `projects` commands require browser-token auth (`ching login` without `--with-key`). API keys are scoped to a single project, so they cannot list or create projects.

Create a product and a recurring price:

```bash
# Create the product
npx @ching-payments/cli products create \
  --name "Pro Plan" \
  --description "Everything in Free, plus advanced reports" \
  --feature "Unlimited reports|Up to 50 members" \
  --feature "Priority support"

# -> prints prod_AbCdEf...

# Create a monthly recurring price (₪49.90/month)
npx @ching-payments/cli prices create \
  --product prod_AbCdEf \
  --amount 4990 \
  --type recurring \
  --interval month \
  --tax-mode inclusive

# Yearly with 14-day trial
npx @ching-payments/cli prices create \
  --product prod_AbCdEf \
  --amount 49900 \
  --type recurring \
  --interval year \
  --trial-days 14
```

For one-time pricing use `--type one_time` and omit `--interval`. For full reference see `references/cli-command-reference.md`.

Create the API key and webhook from the terminal (alternative to the dashboard in Step 1). Both secrets are printed **once** - capture them immediately:

```bash
# Issue an API key (uses the active mode -> ck_test_ in test, ck_live_ in live).
# Requires browser login (ching login); --with-key sessions can't create keys.
npx @ching-payments/cli api-keys create --name "Acme server key"

# Register a webhook in the current mode. Prints the whsec_ signing secret once.
npx @ching-payments/cli webhooks create \
  --url https://acme.com/webhooks/ching \
  --events charge.succeeded charge.failed

# Inspect later (secrets are never re-shown - only masked previews):
npx @ching-payments/cli api-keys list
npx @ching-payments/cli webhooks list
```

Mode-switching mid-shell:

```bash
npx @ching-payments/cli use --test          # switch this shell to test mode
npx @ching-payments/cli use proj_xyz --live # switch project + go live
npx @ching-payments/cli prices list --json  # machine-readable output
```

Live writes prompt for confirmation; pass `--yes` in CI.

The CLI does **not** include a webhook listener. Use ngrok or a tunnel during development to expose your local endpoint.

### Step 3: Authenticate API requests from your server

Every API call goes to `https://api.ching.co.il/ching/v1/<resource>` with `Authorization: Bearer <key>` and `Content-Type: application/json`. There is no SDK yet; use plain `fetch`/`axios`/`requests`.

Reference helper (Node.js):

```js
async function ching(path, init = {}) {
  const res = await fetch(`https://api.ching.co.il/ching/v1${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${process.env.CHING_API_KEY}`,
      'Content-Type': 'application/json',
      ...(init.headers || {}),
    },
  });
  const body = await res.json();
  if (!res.ok || body.success === false) {
    throw new Error(body?.error?.message || `CHING ${res.status}`);
  }
  return body;
}
```

Error shape (always returned with `success: false`):

```json
{
  "success": false,
  "error": {
    "status": 400,
    "code": "INVALID_FIELD",
    "message": "amount must be a positive integer",
    "issues": [{ "path": "amount", "message": "..." }]
  }
}
```

There are no idempotency keys yet; deduplicate writes on your side using a database constraint or a request-hash table.

### Step 4: Run a one-time charge with Checkout Sessions

Server-side, create a session and redirect the user to the returned `url`. The `secured.ching.co.il` page handles cards, Bit, Apple Pay, Google Pay, PayBox, and bank transfer.

A `customer` (`cus_*`) must exist before you create the session - there is no auto-create. Either look up your stored `cus_*` for the logged-in user, or create one inline from the form fields you collected (name/email/phone). If you sync customers from your own system and would rather not track whether each one already exists in CHING, use **upsert** instead of create (see below):

```js
// POST /api/checkout
// 1. Make sure we have a CHING customer id. Persist this in your own DB
//    keyed by your user id so you reuse it across sessions.
const { data: customer } = await ching('/customers', {
  method: 'POST',
  body: JSON.stringify({
    name: `${firstName} ${lastName}`,
    email,
    phone,                          // optional, E.164 preferred
  }),
});

// 2. Create the checkout session against a pre-created price.
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: customer.id,          // REQUIRED — cus_*
    price: 'price_AbCdEf',          // pre-created in CHING
    success_url: 'https://app.example.com/billing/success?cs={CHECKOUT_SESSION_ID}',
    cancel_url: 'https://app.example.com/billing/cancel',
    create_document: true,          // auto-issue a tax invoice
  }),
});
return Response.redirect(session.url, 303);
```

#### Updating and upserting customers

To change an existing customer, `POST /customers/:id` with only the fields you want to change (patch semantics; omitted fields are untouched). Returns `404` if the id does not exist.

```js
await ching(`/customers/${customerId}`, {
  method: 'POST',
  body: JSON.stringify({ email: 'new@example.com', taxId: '514999874' }),
});
```

To create-or-update in one call, `POST /customers/upsert` with an `identifyBy` of `email`, `taxId`, or `phone`. CHING looks up an existing customer in the current mode by that field; if found it patches it, otherwise it creates a new one. The response carries `action: "created" | "updated"`. `name` is required only when a new customer is created. Phone values are normalized to E.164 before matching, so `054-987-6543` matches a stored `+972549876543`. If more than one customer matches, the most recently created one is updated.

```js
const { data: customer, action } = await ching('/customers/upsert', {
  method: 'POST',
  body: JSON.stringify({
    identifyBy: 'email',           // 'email' | 'taxId' | 'phone'
    email,                          // the match key - must be present
    name: `${firstName} ${lastName}`,
    phone,
  }),
});
// action === 'created' or 'updated'; customer.id is the cus_* either way
```

Updates and upsert-matches emit `customer.updated`; an upsert that creates emits `customer.created`.

To remove a customer, `DELETE /customers/:id`. This is a **soft delete**: the record is tombstoned, not erased - all charges, documents, and subscriptions keep referencing it so your financial history stays intact, and saved cards are detached. If the customer has a subscription in `active`, `trialing`, or `past_due`, the call returns `409` (`CUSTOMER_HAS_ACTIVE_SUBSCRIPTION`); cancel the subscription first, then delete. After deletion the customer drops out of `list`, is skipped by `upsert` matching, can no longer be updated, and `GET` returns `{ id, object: "customer", deleted: true }`. Emits `customer.deleted`. The call is idempotent.

```js
await ching(`/customers/${customerId}`, { method: 'DELETE' });
// -> { success: true, data: { id, object: 'customer', deleted: true } }
```

For a cart, drop `price` and pass `line_items` instead. The mode is decided by which keys you send, there is **no `mode` field**:

- `price` alone -> a single charge or a subscription against a pre-created price
- `line_items` alone -> an ad-hoc cart
- `price` **and** `line_items` together -> **mixed checkout** (a recurring plan plus one-time line items in one session, see below)

```js
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: customer.id,
    line_items: [
      { name: 'Nintendo Switch 2', amount_agorot: 149900, quantity: 1,
        description: 'Console', image_url: 'https://shop.example.com/switch2.png' },
      { name: 'Xbox Elite Controller', amount_agorot: 59900, quantity: 1 },
    ],
    success_url: 'https://shop.example.com/checkout/success?cs={CHECKOUT_SESSION_ID}',
    cancel_url: 'https://shop.example.com/checkout/cancel',
    create_document: true,
  }),
});
```

`line_items` accepts `name` (required), `amount_agorot` (required, signed - negatives render as discount lines), `quantity` (default 1, max 1000), `description?`, `image_url?` (must be https://), and optionally `price?` / `product?`. The cart total across all lines must be >= 0.

**Line items and discounts.** A line item is ad-hoc by default - just a name and an amount - and carries **no link to a CHING product or price**. A discount that targets a specific product or price therefore will **not** apply to a bare line item (only order-level discounts reach it). To make a line item eligible for a product/price-targeted discount, set its `price` (the CHING price id it represents; this also resolves the parent product) or `product` (a product id). An unknown id is rejected with `line_item_target_not_found`.

- **Selling CHING-catalog items** (e.g. a setup-fee price you created in CHING, or one-time products you discount): send `price` (or `product`) on each line item so your discounts apply.
- **Pure e-commerce carts** whose SKUs are NOT CHING products: leave `price`/`product` off. You aren't charging for CHING-created products, so there's nothing to link - those items simply aren't eligible for product/price-targeted discounts (order-level discounts still apply).

Sessions expire **30 minutes** after creation; create a fresh one per checkout attempt. Do not reuse session URLs.

After the customer pays, CHING posts `charge.succeeded` to your webhook (Step 7). The redirect to `success_url` is for UX only; never grant entitlements based on the redirect alone.

#### Mixed checkout (recurring plan + one-time line items)

Send **both** `price` and `line_items` to bill a subscription and ad-hoc one-time items in a single session - e.g. a monthly plan plus a one-time setup fee or onboarding session. There is no `mode` field; sending both keys selects this branch.

```js
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: customer.id,
    price: 'price_recurringMonthly',  // MUST be a recurring price
    line_items: [
      // `price` links the line to its CHING price (and parent product) so
      // product/price-targeted discounts apply. Omit it for ad-hoc items.
      { name: 'Setup fee', amount_agorot: 4900, quantity: 1, price: 'price_setupFee' },
      { name: 'Onboarding session', amount_agorot: 12000, quantity: 1, price: 'price_onboarding' },
    ],
    success_url: 'https://app.example.com/billing/success?cs={CHECKOUT_SESSION_ID}',
    cancel_url: 'https://app.example.com/billing/cancel',
    create_document: true,
  }),
});
return Response.redirect(session.url, 303);
```

Rules and behaviour:

- **The `price` must be recurring.** A one-time price plus `line_items` is rejected with `mixed_requires_recurring_price` (that combination is just a cart, use `line_items` alone).
- **`line_items` is the same shape as a cart**: 1 to 50 items, `amount_agorot` is signed (negatives are discount lines), and the total across all lines must be `>= 0` (`cart_total_invalid` otherwise).
- **For discounts to apply to the one-time items, set each item's `price` (or `product`).** Without it the line is ad-hoc and only order-level discounts reach it (see "Line items and discounts" above). Not needed for e-commerce SKUs that aren't CHING products.
- **`capture_method: 'manual'` is rejected** (`capture_method_not_supported_for_mixed`). Mixed always settles through the saved-card flow because it must store a card for renewals; a J5 hold can't authorize a recurring token. Express wallets are disabled on mixed sessions for the same reason.
- **Billing timing depends on the trial:**
  - No trial -> the customer is charged `line_items_total + plan_first_period` immediately and the subscription starts `active`.
  - Trial -> only `line_items_total` is charged now, the subscription starts `trialing`, and the plan's first period is charged when the trial ends (via the normal renewal cron).
- The public session (`GET /checkout_sessions/:id/public`, used by the hosted page) exposes a `billing_summary` for mixed sessions: `amount_due_now`, `one_time_amount_due_now`, `subscription_amount_due_now` (0 during a trial), `subscription_amount_due_later`, `trial_period_days`, `trial_end`.

After the customer pays you receive `subscription.created` followed by `charge.succeeded` (or `charge.failed` if the immediate charge declines, in which case the subscription is left `incomplete` and the session stays open for retry). Fulfil on the webhooks, never on the redirect. See Step 6 for the subscription lifecycle and Step 7 for the events.

#### Authorize now, capture later (J4J5 manual capture)

For ecommerce where the final amount isn't known at checkout (variable-weight goods, made-to-order, stock confirmation required), pass `capture_method: 'manual'` on the checkout session. CHING authorizes the card via Grow's J5 hold and waits for an explicit `POST /v1/charges/:id/capture` (within 7 days) - no money moves until you capture.

```js
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: customer.id,
    line_items: [{ name: 'Sea bass (per kg)', amount_agorot: 12000, quantity: 1 }],
    capture_method: 'manual',     // J5 hold, not immediate charge
    success_url: '...',
    cancel_url: '...',
  }),
});
```

After the customer pays, you receive `charge.authorized` (NOT `charge.succeeded`) and have ~7 days. Then either:

```js
// Stock confirmed - capture (full or partial; unused balance auto-released).
await ching(`/charges/${chargeId}/capture`, {
  method: 'POST',
  body: JSON.stringify({ amount: 13400 }),  // omit for full capture
});
// charge.captured fires; receipt emails + tax document issue here.

// Or, order canceled - release the hold.
await ching(`/charges/${chargeId}/cancel`, {
  method: 'POST',
  body: JSON.stringify({ cancellation_reason: 'requested_by_customer' }),
});
// charge.canceled fires.
```

Constraints to remember:
- Only valid for one-time prices and carts with a new card. Recurring prices are rejected; saved cards and express wallets (Apple Pay / Bit / Google Pay) ignore the flag and stay automatic.
- Cancellation releases the CHING-side record immediately, but the customer's bank may take up to **10 days** to remove the hold from their available balance (Grow's auto-release window). Tell your customer this.
- The daily sweep auto-cancels held charges at `capturable_until` (~7 days) with `cancellation_reason: 'expired'`.

### Step 5: Save a card without charging (Setup Sessions)

Use Setup Sessions when you need a card on file before billing (free trials, post-paid usage, recurring without immediate charge).

```js
const setup = await ching('/setup_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: 'cus_XyZ',
    success_url: 'https://app.example.com/onboarding/done',
    cancel_url: 'https://app.example.com/onboarding/card',
    metadata: { signupFlow: 'trial-v3' },
  }),
});
return Response.redirect(setup.url, 303);
```

Setup sessions expire after **24 hours**. On success the new payment method (`pm_*`) is attached to the customer and `payment_method.attached` fires.

To list a customer's cards:

```js
const { data } = await ching(`/customers/cus_XyZ/payment_methods`);
// [{ id: 'pm_...', brand: 'visa', last4: '4242', exp_month: 12, exp_year: 2030 }, ...]
```

### Step 6: Subscriptions (recurring billing)

Once the customer has a `pm_*`, you can create a subscription against a recurring price.

```js
const sub = await ching('/subscriptions', {
  method: 'POST',
  body: JSON.stringify({
    customer: 'cus_XyZ',
    price: 'price_recurringMonthly',
    payment_method: 'pm_AbCd',   // optional if price has trial; required after trial
  }),
});
// sub.status: 'trialing' | 'active' | 'incomplete'
```

Status lifecycle:
- `trialing` (price had `trial_period_days`) -> `active` after first successful charge
- `incomplete` if first charge fails; auto-expires to `incomplete_expired` after **23 hours**
- `active` -> `past_due` if a renewal fails (retries day 3, 7, 14) -> `canceled` after final failure
- `subscription.trial_will_end` fires 3 days before trial ends; surface a "add card" CTA

Cancel:

```js
await ching(`/subscriptions/sub_AbCd/cancel`, { method: 'POST' });
```

Show the upcoming charge: `GET /subscriptions/:id` returns a next-charge estimate so you can render the renewal price (with any discount) in your UI:

```js
const { data: sub } = await ching('/subscriptions/sub_AbCd');
// next_charge_subtotal:        41300  // gross before discounts (agorot)
// next_charge_discount_amount: 18054  // total reduction
// next_charge_amount:          23246  // what will actually be charged (subtotal - discount)
// next_charge_discounts: [
//   { name: 'Reserve duty fair', value_type: 'override', value: 19700,
//     duration: 'forever', charges_remaining: null, ends_at: null, amount_off: 18054 },
// ]
```

`next_charge_discounts` lists each discount reducing that charge. `charges_remaining` is set only for `n_charges` (discounted charges left, including the upcoming one); `ends_at` only for `until_date`; both are null for `once`/`forever`. The array is empty when nothing applies and drops a discount once it completes or expires - so it always reflects the live next charge. These `next_charge_*` fields are on the single GET only, not on list or create.

### Step 6b: Discounts and coupons (optional)

A **discount rule** (`disc_*`) reduces what a customer pays. Create it once, then it applies either **automatically** (whenever a matching product/price/order is bought) or via a **code** the customer enters. Rules target the whole `order`, specific `products`, or specific `prices`, and carry a `duration` (`once`, `n_charges`, `until_date`, `forever`) that controls how long they keep reducing a subscription's charges.

```js
// A "code" rule: 25% off a specific plan, for the first 3 charges.
const disc = await ching('/discounts', {
  method: 'POST',
  body: JSON.stringify({
    name: 'Launch 25%',
    redemption: 'code',
    code: 'LAUNCH25',          // UPPERCASE, [A-Z0-9_-], not unique
    target_type: 'prices',
    targets: ['price_recurringMonthly'],
    value_type: 'percent',
    value: 2500,               // basis points: 2500 = 25%
    duration: 'n_charges',
    duration_charges: 3,
  }),
});
// disc.id -> "disc_..."
```

`value_type` is `percent` (basis points), `amount` (agorot off; needs `currency`), or `override` (agorot target unit price; needs `currency`, optional `value_tax_mode`). Only `name`, `active`, the active window, the redemption caps, and `metadata` are editable after creation - value/type/target/duration are frozen so already-applied discounts keep their terms. Archive a rule with `POST /discounts/:id/archive`; already-attached discounts run out their own duration.

Apply a code three ways:

```js
// 1. Pre-applied on a hosted checkout session (shows as a removable chip).
await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({ customer, success_url, cancel_url, price, coupon_codes: ['LAUNCH25'] }),
});

// 2. On the hosted page itself (public, no auth): POST /checkout_sessions/:id/discount { code }
//    and DELETE /checkout_sessions/:id/discount/:code to remove. The public GET
//    returns a live discount preview (discounts, discount_lines, total_discount_agorot).

// 3. Directly when creating a subscription over the API:
await ching('/subscriptions', {
  method: 'POST',
  body: JSON.stringify({
    customer, price: 'price_recurringMonthly', payment_method,
    discounts: [{ code: 'LAUNCH25' }],   // or { discount: 'disc_...' }
  }),
});
```

Each attached rule becomes an **applied discount** (`di_*`, status `active` → `completed`/`canceled`). The webhooks are `discount.created`/`updated`/`deleted` (rule lifecycle) and `discount.applied`/`discount.expired` (per-subscription). See `references/api-endpoints.md` for the full field list and `references/webhook-events.md` for payloads.

### Step 7: Verify and handle webhooks

This is the single most important security step. Verify every webhook with HMAC-SHA256 over the raw body.

```js
import crypto from 'node:crypto';

export function verifyChingSignature(rawBody, header, secret) {
  const expected = crypto
    .createHmac('sha256', secret)
    .update(rawBody)
    .digest('hex');
  // header value: hex string. Use timing-safe comparison.
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(header || '', 'hex');
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// Express handler - body MUST be the raw bytes, not a parsed object
app.post('/webhooks/ching',
  express.raw({ type: 'application/json' }),
  (req, res) => {
    const sig = req.header('Ching-Signature');
    if (!verifyChingSignature(req.body, sig, process.env.CHING_WEBHOOK_SECRET)) {
      return res.status(400).send('invalid signature');
    }
    const event = JSON.parse(req.body.toString('utf8'));
    handleEvent(event); // dispatch by event.type
    res.json({ received: true });
  });
```

Python helper is bundled at `scripts/verify-webhook.py`.

Event types you must handle for a basic SaaS:

| Event | Action |
|-------|--------|
| `charge.succeeded` | Grant entitlement, send receipt |
| `charge.failed` | Notify customer, log for retry analytics |
| `charge.authorized` | (J4J5 only) Mark the order as "card authorized, awaiting capture." Do NOT fulfil yet - no funds have moved. |
| `charge.captured` | (J4J5 only) Funds captured; fulfil the order. Payload has `amount_captured` which may be less than `amount` on partial capture. |
| `charge.canceled` | (J4J5 only) Authorization released. Free any held stock. `data.cancellation_reason` tells you why (`requested_by_customer` / `fraudulent` / `abandoned` / `expired`). |
| `payment_method.attached` | Update saved-card UI |
| `payment_method.detached` | Refresh saved-card UI |
| `subscription.created` | Provision plan |
| `subscription.updated` | Sync status (`active`, `past_due`, `canceled`) |
| `subscription.canceled` | Revoke entitlement at period end |
| `subscription.trial_will_end` | Email "add card" CTA |
| `setup_session.failed` | Show retry UI |
| `setup_session.expired` | Show retry UI |
| `refund.created` | Update internal accounting |
| `discount.applied` | (if you use coupons) A discount attached to a subscription; payload is an `applied_discount` |
| `discount.expired` | (if you use coupons) A subscription discount's duration ran out; charges return to full price |

Full payload structure and the complete event catalog are in `references/webhook-events.md`.

### Step 8: Refunds

```js
await ching('/refunds', {
  method: 'POST',
  body: JSON.stringify({
    charge: 'ch_AbCd',
    amount_agorot: 4990,           // omit for full refund
    reason: 'requested_by_customer', // | 'duplicate' | 'fraudulent'
  }),
});
```

Refunds are async; the `refund.created` webhook fires when the bank confirms.

### Step 9: Customer self-service Billing Portal

Send an authenticated customer to a hosted portal where they can manage cards, subscriptions, and download invoices.

```js
const portal = await ching('/billing_portal_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: 'cus_XyZ',
    return_url: 'https://app.example.com/account',
  }),
});
return Response.redirect(portal.url, 303);
```

Portal tokens expire after **~1 hour**. Re-create per visit; do not cache the URL.

### Step 10: Test the integration end-to-end

1. With a test API key, create a customer and a setup session.
2. Open the returned URL, use the sandbox card flow at `secured.ching.co.il` to attach a card.
3. Trigger `payment_method.attached` arrives at your webhook.
4. Create a subscription against a recurring price.
5. Verify `subscription.created` and the immediate `charge.succeeded`.
6. Issue a refund, verify `refund.created`.
7. Open the Billing Portal, cancel the subscription, verify `subscription.canceled`.

Dev tunnels: use `ngrok http 3000` (or `cloudflared tunnel`) and paste the public URL into the dashboard webhook config. Do not point production webhooks at a tunnel.

## Examples

### Example 1: "Add CHING checkout to my Next.js app"

User says: "I want to add a Pro plan ₪49.90/mo via CHING checkout to my Next.js app."

Actions:
1. Have the user create the project, API key, and webhook in the dashboard (Step 1).
2. Install nothing, but use `npx @ching-payments/cli` to create the product and recurring price (Step 2).
3. Add an API route `app/api/checkout/route.ts` that calls `POST /v1/checkout_sessions` and `Response.redirect`s (Step 4).
4. Add `app/api/webhooks/ching/route.ts` with HMAC verification using the bundled `scripts/verify-webhook.py` pattern (Step 7).
5. On `subscription.created`, set the user's plan in the database.
6. On `subscription.canceled`, schedule downgrade for `current_period_end`.

Result: working subscription flow, fulfillment driven entirely by webhooks.

### Example 2: "Save a card during onboarding, charge later"

User says: "I want to collect a card during signup but only charge for usage at month end."

Actions:
1. Create the customer in your signup flow: `POST /v1/customers`.
2. Create a Setup Session right after, redirect to `setup.url` (Step 5).
3. On `payment_method.attached`, mark the customer "billable" in your DB.
4. End of month, compute usage in agorot and call `POST /v1/charges` with `customer`, `payment_method` (the saved `pm_*`), `amount`, `description`.
5. On `charge.succeeded`, mark the invoice as paid.

Result: usage-based billing without holding card numbers.

### Example 3: "Refund a customer who cancelled within 14 days"

User says: "Customer wants their money back, they signed up 5 days ago for ₪199."

Actions:
1. Look up the charge ID in your system (or `GET /v1/charges?customer=cus_XyZ`).
2. Issue a refund: `POST /v1/refunds` with `charge: 'ch_...'`, `reason: 'requested_by_customer'`.
3. Cancel the subscription: `POST /v1/subscriptions/sub_.../cancel`.
4. On `refund.created`, send a confirmation email and update accounting.
5. On `subscription.canceled`, revoke entitlement.

Result: clean refund + cancel handled in 4 webhook events.

### Example 4: "Ecommerce store with variable-weight goods (J4J5 manual capture)"

User says: "We sell fish by the kilo; the final price depends on what we actually pack. I want to authorize the card at checkout and charge the real amount after we pack the order."

Actions:
1. Create the checkout session with `capture_method: 'manual'` and `line_items` for the estimated cart (Step 4 - "Authorize now, capture later").
2. Customer pays on the hosted page; you receive `charge.authorized` (not `charge.succeeded`). Mark the order "card authorized, awaiting fulfilment" in your DB.
3. Your fulfilment team weighs and packs the goods.
4. Call `POST /v1/charges/:id/capture` with `amount` set to the real total in agorot (or omit for full capture). The difference is auto-released to the customer's card.
5. On `charge.captured`, mark the order paid and shipping. Receipt and tax document fire automatically at capture time.
6. If the order is canceled before capture, call `POST /v1/charges/:id/cancel` with a `cancellation_reason`. The CHING-side hold releases immediately; warn the customer the bank may hold the funds for up to 10 days regardless.

Reminder: capture/cancel windows close 7 days after authorization (CHING auto-cancels with `cancellation_reason: 'expired'`).

Result: authorize-then-capture flow with no money moving until fulfilment is confirmed.

### Example 5: "Charge a setup fee alongside a new subscription (mixed checkout)"

User says: "When someone signs up for our ₪99/mo plan I also want to bill a one-time ₪49 setup fee in the same checkout."

Actions:
1. Make sure the customer exists (`POST /customers`) and the recurring price is created (`price_*`, ₪99/mo).
2. Create one checkout session passing **both** `price` (the recurring plan) and `line_items` (the ₪49 setup fee) - this is mixed checkout (Step 4 - "Mixed checkout"). Redirect to `session.url`.
3. Customer pays on the hosted page. With no trial, CHING charges ₪148 now (plan first period + setup fee) and you receive `subscription.created` (status `active`) then `charge.succeeded`.
4. On `subscription.created`, provision the plan. The setup fee needs no separate handling - it rode along on the same charge and its own tax document is issued automatically.
5. If the price has a trial, only the ₪49 setup fee is charged now (status `trialing`); the plan's first ₪99 is charged when the trial ends.

Result: plan + one-time fee collected in a single redirect, fulfilment driven by the subscription and charge webhooks.

## Bundled Resources

### Scripts
- `scripts/verify-webhook.py` -- Verifies the `Ching-Signature` header against a raw payload using HMAC-SHA256. Useful for one-off debugging or as a reference implementation. Run: `python3 scripts/verify-webhook.py --help`
- `scripts/agorot-converter.py` -- Converts between shekels and agorot to avoid the off-by-100 bug. Run: `python3 scripts/agorot-converter.py --help`

### References
- `references/api-endpoints.md` -- Complete endpoint catalog: every public REST route with method, path, required and optional fields, and ID prefix conventions. Consult when building a new API call or debugging a 4xx response.
- `references/webhook-events.md` -- Every webhook event type with payload shape, lifecycle, and retry semantics. Plus the full HMAC verification algorithm. Consult when wiring or debugging webhook handlers.
- `references/cli-command-reference.md` -- Every `@ching-payments/cli` command with all flags and example invocations. Consult when scripting catalog operations or building deploy automation.

## Reference Links

Official sources for verifying and updating the information in this skill:

| Source | URL | What to Check |
|--------|-----|---------------|
| CHING marketing site | https://ching.co.il | Product positioning, pricing tiers |
| CHING merchant dashboard | https://app.ching.co.il | API keys, webhooks, products, customers |
| CHING API root | https://api.ching.co.il | Health check; the public REST API lives under `/ching/v1` (requires `Authorization: Bearer ck_...`) |
| CHING CLI on npm | https://www.npmjs.com/package/@ching-payments/cli | Latest CLI version, install command |
| Israeli VAT rules (gov.il) | https://www.gov.il/he/departments/israel_tax_authority | Current VAT rate, invoice requirements |

## Gotchas

- Amounts in API requests are in **agorot**, not shekels. ₪49.90 is `4990`. Multiplying by 100 at the API boundary, dividing by 100 at the UI boundary. Test by round-tripping a known amount through `scripts/agorot-converter.py`.
- The webhook signature is HMAC-SHA256 over the **raw request body bytes**, not a parsed JSON re-serialization. Frameworks that auto-parse JSON (Express, FastAPI, Next.js route handlers) will silently break verification. Capture the raw body before parsing.
- Checkout sessions expire after 30 minutes, setup sessions after 24 hours, billing portal tokens after ~1 hour. Always create a fresh session per redirect; never cache a session URL.
- The `success_url` redirect is for UX only. Webhook events are the only trustworthy signal of payment success. Never grant entitlement on the success page alone.
- `ck_live_*` keys are blocked until the merchant completes Grow KYC and links a business identity. Local development is always test mode.
- There are no idempotency keys yet. Wrap writes with your own dedupe key (e.g., `INSERT ... ON CONFLICT` on a request hash) to survive retries.
- The CLI has no `listen` command for forwarding webhooks. Use `ngrok` or `cloudflared tunnel` to expose your local endpoint during development.
- Subscription retries run at days 3, 7, and 14 after a failed renewal, then cancel. Build your dunning emails around `subscription.updated` with `status: 'past_due'`.

## Troubleshooting

### Error: 401 with code `WRONG_CREDENTIALS`
Cause: Missing or malformed `Authorization` header, or the key was rotated/deleted in the dashboard.
Solution: Check the header is exactly `Authorization: Bearer ck_test_<64hex>`. Verify the key still exists at https://app.ching.co.il/api-keys. Rotate if compromised.

### Error: 403 with code `LIVE_KEY_INACTIVE`
Cause: Using a `ck_live_*` key before the merchant completed Grow onboarding and business identity linking.
Solution: Either switch to a `ck_test_*` key for development, or have the merchant finish onboarding at https://app.ching.co.il/settings.

### Error: Webhook returns "invalid signature"
Cause: Body was parsed (and re-serialized) before HMAC, or the wrong secret is used (test vs live, or wrong endpoint), or extra middleware mutated the bytes.
Solution: Capture `req.body` as a `Buffer`/`bytes` before any JSON parsing. Use `express.raw({ type: 'application/json' })` or its FastAPI/Next.js equivalent. Confirm the secret matches the endpoint and mode.

### Error: Customer says "I paid but nothing happened"
Cause: Code is granting entitlement on the `success_url` redirect (which the customer may have closed) instead of the `charge.succeeded` webhook.
Solution: Move all fulfillment into the webhook handler. The success page should only display "thanks, check your email".

### Error: Subscription stuck in `incomplete`
Cause: First charge failed; subscription is waiting for a successful payment within 23 hours.
Solution: Either let it auto-expire to `incomplete_expired` and create a new one, or have the customer update their card via the Billing Portal (a successful charge there moves it to `active`).
