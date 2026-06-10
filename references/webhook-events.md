# CHING Webhook Events Reference

CHING posts JSON payloads to your registered HTTPS endpoint when events happen. Each request includes a signature header you must verify before trusting the payload.

## Envelope

Every event has the same outer shape:

```json
{
  "id": "evt_AbCdEf123",
  "type": "charge.succeeded",
  "data": { /* resource snapshot, see below */ },
  "livemode": false,
  "created": "2026-05-09T10:23:11.000Z"
}
```

- `id` is unique. Use it as a dedupe key in your handler.
- `type` is dot-namespaced (resource.action).
- `livemode` matches the API key the event originated from. Test events never appear on live endpoints and vice-versa.

## Signature verification

Header: `Ching-Signature: <hex>`

Algorithm: `HMAC_SHA256(secret = whsec_*, payload = raw request body bytes)` -> hex.

**Critical: HMAC the raw body, never the parsed-then-re-serialized JSON.** Most frameworks parse JSON automatically, mutating bytes (key order, whitespace, escape sequences). You must capture the raw bytes before parsing.

### Node.js (Express)

```js
import crypto from 'node:crypto';
import express from 'express';

const app = express();

app.post('/webhooks/ching',
  express.raw({ type: 'application/json' }),
  (req, res) => {
    const sig = req.header('Ching-Signature') || '';
    const expected = crypto
      .createHmac('sha256', process.env.CHING_WEBHOOK_SECRET)
      .update(req.body)
      .digest('hex');

    const a = Buffer.from(expected, 'hex');
    const b = Buffer.from(sig, 'hex');
    const ok = a.length === b.length && crypto.timingSafeEqual(a, b);
    if (!ok) return res.status(400).send('invalid signature');

    const event = JSON.parse(req.body.toString('utf8'));
    handleEvent(event);
    res.json({ received: true });
  });
```

### Next.js (App Router)

```ts
import { NextRequest } from 'next/server';
import crypto from 'node:crypto';

export const runtime = 'nodejs';

export async function POST(req: NextRequest) {
  const raw = Buffer.from(await req.arrayBuffer());
  const sig = req.headers.get('ching-signature') || '';
  const expected = crypto
    .createHmac('sha256', process.env.CHING_WEBHOOK_SECRET!)
    .update(raw)
    .digest('hex');
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(sig, 'hex');
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return new Response('invalid signature', { status: 400 });
  }
  const event = JSON.parse(raw.toString('utf8'));
  await handleEvent(event);
  return Response.json({ received: true });
}
```

### Python (FastAPI)

```python
import hmac, hashlib, os
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

@app.post('/webhooks/ching')
async def ching_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get('ching-signature', '')
    expected = hmac.new(
        os.environ['CHING_WEBHOOK_SECRET'].encode(),
        raw,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(400, 'invalid signature')
    event = await request.json()
    await handle_event(event)
    return {'received': True}
```

A standalone CLI verifier is bundled at `scripts/verify-webhook.py`.

## Event catalog

| Type | When it fires | `data` resource |
|------|---------------|-----------------|
| `charge.succeeded` | A charge completed and funds settled (or are reserved on the card). | Charge (`ch_*`) |
| `charge.failed` | A charge attempt was declined. `data.failure_reason` carries the cause. | Charge |
| `charge.authorized` | A manual-capture (J5) charge was authorized but not yet captured. Payload carries `capture_method: "manual"`, `authorized_at`, `capturable_until`. The merchant must call `POST /charges/:id/capture` or `/cancel` within ~7 days. | Charge |
| `charge.captured` | A previously-authorized charge was captured. Payload carries `amount_captured` (may be < `amount` on partial capture - the unused balance was released to the customer). Receipt emails and tax document issuance happen at this point, not at authorization. | Charge |
| `charge.canceled` | A held authorization was canceled - either by `POST /charges/:id/cancel` or automatically by the daily sweep at `capturable_until`. `data.cancellation_reason` is one of `requested_by_customer`, `fraudulent`, `abandoned`, `expired`. | Charge |
| `payment_method.attached` | A card was saved on a customer (via Setup Session, test card mint, or Billing Portal). | Payment method (`pm_*`) |
| `payment_method.detached` | A saved card was removed (by merchant, customer, or expiry). | Payment method |
| `refund.created` | A refund was issued and the bank confirmed (or final state determined). | Refund (`re_*`) |
| `subscription.created` | A subscription was created. | Subscription (`sub_*`) |
| `subscription.updated` | Status or price changed. Includes the new and previous status. | Subscription |
| `subscription.canceled` | Subscription canceled (by merchant, customer, or after dunning failure). | Subscription |
| `subscription.trial_will_end` | Fires 3 days before `trial_end`. Use to email an "add card" CTA. | Subscription |
| `setup_session.failed` | The customer entered card details but the save failed. | Setup session (`seti_*`) |
| `setup_session.expired` | 24h passed and the customer never opened or completed the session. | Setup session |
| `customer.created` | A customer was created (`POST /customers` or upsert with no match). | Customer (`cus_*`) |
| `customer.updated` | A customer's details changed (`POST /customers/:id` or upsert that patched a match). | Customer |
| `customer.deleted` | A customer was soft-deleted via `DELETE /customers/:id`. | Customer |
| `discount.created` | A discount rule was created via `POST /discounts`. | Discount (`disc_*`) |
| `discount.updated` | A rule's mutable fields or its targets changed. | Discount |
| `discount.deleted` | A rule was archived (soft-deleted) via `POST /discounts/:id/archive`. | Discount |
| `discount.applied` | A rule was attached to a subscription (at checkout-confirm or subscription create) and became an applied-discount. `data` is an `applied_discount`: `{ object, subscription, discount_row_id, livemode, created }`. | Applied discount |
| `discount.expired` | An applied-discount's `duration` ran out at a renewal (its `status` moved to `completed`); it no longer reduces future charges. Same `applied_discount` payload. | Applied discount |

## Lifecycle examples

### Successful subscription signup
```
subscription.created           (status: incomplete)
charge.succeeded               (first invoice paid)
subscription.updated           (status: active)
```

### Trial signup
```
payment_method.attached        (Setup session converted)
subscription.created           (status: trialing, trial_end set)
[3 days before trial_end]
subscription.trial_will_end
[on trial_end]
charge.succeeded               (first paid period)
subscription.updated           (status: active)
```

### Mixed checkout (recurring plan + one-time line items)
Created by sending both `price` (recurring) and `line_items` to `/checkout_sessions`. The subscription event fires first, then the immediate charge.

No trial - line items + first plan period charged together:
```
subscription.created           (status: active)
charge.succeeded               (line items + plan first period)
```
With a trial - only the one-time line items are charged now; the plan is charged at trial end:
```
subscription.created           (status: trialing, trial_end set)
charge.succeeded               (line items only)
[on trial_end]
charge.succeeded               (first plan period)
subscription.updated           (status: active)
```
If the immediate charge declines, the subscription is left `incomplete` and the session stays open for retry (a retry reuses the same subscription and emits `subscription.updated` instead of `subscription.created`):
```
subscription.created           (status: incomplete)
charge.failed
```

### Discounted subscription (e.g. "50% off for 3 charges")
A code is applied at checkout (or `discounts` passed to `POST /subscriptions`), the rule attaches as an applied-discount, then expires once its `duration` runs out.
```
subscription.created           (status: active)
discount.applied               (applied_discount attached, status: active)
charge.succeeded               (first period, reduced)
[renewal 2]
charge.succeeded               (reduced)
[renewal 3]
charge.succeeded               (reduced - 3rd and last reduced charge)
discount.expired               (applied_discount completed)
[renewal 4]
charge.succeeded               (full price)
```

### Manual capture (J4J5)
```
charge.authorized              (Grow J5 hold, awaiting capture or cancel)
[merchant calls POST /charges/:id/capture]
charge.captured                (funds captured; tax document + receipt issued)
```
Or:
```
charge.authorized
[merchant calls POST /charges/:id/cancel]
charge.canceled                (cancellation_reason: requested_by_customer | fraudulent | abandoned)
```
Or, if no action by `capturable_until`:
```
charge.authorized
[7 days pass]
charge.canceled                (cancellation_reason: expired)
```

### Failed renewal and dunning
```
charge.failed                  (renewal attempt)
subscription.updated           (status: past_due)
[day 3]
charge.failed
[day 7]
charge.failed
[day 14]
charge.failed
subscription.updated           (status: canceled)
subscription.canceled
```

## Retry behaviour

CHING retries failed webhook deliveries (non-2xx responses) with exponential backoff for up to 3 days. Your handler should:

1. Verify the signature first. Reject 400 on mismatch (do not retry-storm the merchant).
2. Look up `event.id` in your `processed_events` table. If seen, return 200 immediately (idempotency).
3. Process the event. If transient failure, return 5xx so CHING retries.
4. Insert `event.id` into `processed_events` only after successful processing.

## Common pitfalls

- **Body parser ate the bytes.** Always use raw body middleware on the webhook route, even if every other route uses JSON parsing.
- **Wrong secret.** Each webhook endpoint has its own secret. Test and live endpoints differ. If you rotated, the dashboard generates a new one.
- **Clock skew.** No timestamp tolerance check is required (the signature alone authenticates), but if you add one, allow at least 5 minutes.
- **Reordering.** Events are not guaranteed to arrive in order. Use `event.created` to discard stale updates.
- **Test cards in live.** Test card payment methods cannot be attached to live customers. Sandbox only.
