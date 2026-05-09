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
| `payment_method.attached` | A card was saved on a customer (via Setup Session, test card mint, or Billing Portal). | Payment method (`pm_*`) |
| `payment_method.detached` | A saved card was removed (by merchant, customer, or expiry). | Payment method |
| `refund.created` | A refund was issued and the bank confirmed (or final state determined). | Refund (`re_*`) |
| `subscription.created` | A subscription was created. | Subscription (`sub_*`) |
| `subscription.updated` | Status or price changed. Includes the new and previous status. | Subscription |
| `subscription.canceled` | Subscription canceled (by merchant, customer, or after dunning failure). | Subscription |
| `subscription.trial_will_end` | Fires 3 days before `trial_end`. Use to email an "add card" CTA. | Subscription |
| `setup_session.failed` | The customer entered card details but the save failed. | Setup session (`seti_*`) |
| `setup_session.expired` | 24h passed and the customer never opened or completed the session. | Setup session |

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
