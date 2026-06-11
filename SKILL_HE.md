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
compatibility: >-
  Requires Node.js >=18 for the @ching-payments/cli, an HTTPS endpoint
  for receiving webhooks, and outbound network access to api.ching.co.il
  and secured.ching.co.il. Works with Claude Code, Claude.ai, Cursor,
  and any agent that can run shell commands.
---

# אינטגרציית תשלומי CHING

CHING היא מערכת תשלומים ישראלית עם REST API מודרני ועמודי checkout, setup ופורטל לקוחות מאוחסנים. הסקיל הזה מלווה אותך באינטגרציה מקצה לקצה: יצירת קטלוג מוצרים בעזרת ה-CLI, חיוב חד-פעמי ב-Checkout, שמירת אמצעי תשלום ב-Setup, מנויים, אימות וובהוקים, והפעלת פורטל הלקוחות.

## מודל מנטלי

לקרוא פעם אחת ולחזור לפי הצורך.

| מושג | מה זה ב-CHING |
|------|---------------|
| Project | חשבון סוחר חי. מחזיק מפתחות וקונפיגורציה |
| API key | `ck_test_<64hex>` או `ck_live_<64hex>`. נשלח ב-`Authorization: Bearer <key>` |
| Product | משהו שמוכרים ("חבילת Pro", "ייעוץ של שעה") |
| Price | סכום באגורות מקושר למוצר. one_time או recurring |
| Customer | המשלם הסופי (cus_*) |
| Payment Method | כרטיס שמור על לקוח (pm_*) |
| Checkout Session | עמוד מאוחסן לחיוב או עגלה (co_*) |
| Setup Session | עמוד מאוחסן ששומר כרטיס בלי לחייב (seti_*) |
| Subscription | חיוב חוזר על כרטיס שמור (sub_*) |
| Charge | ניסיון תשלום בודד (ch_*) |
| Refund | החזר חלקי או מלא (re_*) |
| Billing Portal | עמוד ניהול עצמי ללקוח |
| Webhook | POST חתום ל-endpoint שלכם בעת התרחשות אירוע |

שלושת הכללים החשובים שמונעים את רוב הבאגים:

1. סכומים תמיד באגורות, אף פעם לא בשקלים. ₪49.90 הם 4990. כפל ב-100 בקצה ה-API, חלוקה ב-100 בקצה ה-UI.
2. Checkout ו-Setup הם redirect בלבד. יוצרים session בצד השרת, מפנים את הלקוח ל-`url` שחוזר, ומקבלים את התוצאה דרך וובהוק. ה-`success_url` הוא ל-UX בלבד; אסור לסמוך על פרמטרים מה-URL הזה לצורך מתן הרשאות.
3. יוצרים את הלקוח פעם אחת, שומרים את מזהה ה-`cus_*` שלו על רשומת המשתמש שלכם, ומשתמשים בו שוב בכל פעולה בשם אותו אדם - checkout sessions, setup sessions, מנויים, חיובים ו-billing portal. מזהה ה-`cus_*` הוא הידית הקבועה שמקשרת הכול: כרטיסים שמורים, מנויים (ולכן התוכנית הנוכחית של המשתמש), היסטוריית חיובים ומסמכי מס - כולם תלויים בו. אם משתמשים בו שוב, התוכנית של המשתמש ועמודי ה-billing portal שלו נשמרים לאורך זמן; אם יוצרים לקוח חדש בכל פעם, מפצלים את אותו אדם לרשומות מנותקות - לקוחות כפולים, כרטיס ששמור על אחד אך חיוב על אחר, מנוי "נעלם", ופורטל שלא מציג כלום. אדם אחד במערכת שלכם = לקוח CHING אחד, לתמיד.

## הוראות

### שלב 1: הרשמה והגדרת לוח הבקרה של הסוחר

מבקשים מהמשתמש להיכנס ל-https://app.ching.co.il ולבצע:

1. רישום חשבון (אימייל + סיסמה או Google OAuth). מספקים שם עסק, מספר עוסק (מס' ה"פ), וסוג עסק (`COMPANY`, `MURSHE`, `PATOOR`).
2. נשארים במצב Test (כפתור בסרגל העליון) לפיתוח.
3. Settings -> API Keys (`/api-keys`), יוצרים מפתח. הערך המלא מוצג פעם אחת בלבד; מעתיקים מיד. פורמט: `ck_test_<64 hex>`.
4. Settings -> Webhooks (`/webhooks`), מוסיפים endpoint HTTPS של הסוחר ובוחרים סוגי אירועים (או `["*"]`). מעתיקים את הסוד `whsec_<hex>` פעם אחת ומאחסנים כ-`CHING_WEBHOOK_SECRET`.

שלבים 3 ו-4 אפשר לבצע גם מהטרמינל עם ה-CLI - `ching api-keys create` ו-`ching webhooks create` שניהם מדפיסים את הסוד פעם אחת בלבד, בדיוק כמו לוח הבקרה. ראו שלב 2.

כדי לעבור ל-Live בהמשך, הסוחר חייב להשלים:
- הפעלת ספק תשלומים (KYC ב-iframe של Grow תחת `/settings`)
- קישור זהות עסקית (taxId + שם חברה + סוג)
- אז לוח הבקרה משחרר יצירה של מפתחות `ck_live_*`

מנחים את המשתמש להציב את המפתח והסוד במשתני סביבה בשרת בלבד, אף פעם לא בקוד צד הלקוח:

```
CHING_API_KEY=ck_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHING_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHING_API_BASE=https://api.ching.co.il
```

### שלב 2: יצירת מוצרים ומחירים עם ה-CLI

ה-CLI הוא הדרך המהירה ביותר לזריעת קטלוג. רצים עם `npx`, בלי התקנה גלובלית.

```bash
# הזדהות (פותח דפדפן)
npx @ching-payments/cli login

# או הדבקת API key (CI / לא אינטראקטיבי)
npx @ching-payments/cli login --with-key

# בדיקה
npx @ching-payments/cli whoami
```

ניהול projects מהטרמינל (שימושי במיוחד להקמת project staging נפרד):

```bash
# הצגת כל ה-projects בחשבון; הפעיל מסומן
npx @ching-payments/cli projects list

# יצירת project חדש. אם אין project פעיל, החדש מאומץ אוטומטית
npx @ching-payments/cli projects create --name "Acme Staging"

# מעבר כפוי ל-project שזה עתה נוצר
npx @ching-payments/cli projects create --name "Acme EU" --switch
```

פקודות `projects` דורשות אימות browser-token (`ching login` בלי `--with-key`). מפתחות API מקושרים ל-project יחיד, ולכן לא יכולים להציג רשימה או ליצור projects.

יצירת מוצר ומחיר חודשי:

```bash
# יצירת המוצר
npx @ching-payments/cli products create \
  --name "Pro Plan" \
  --description "All Free features plus advanced reports" \
  --feature "Unlimited reports|Up to 50 members" \
  --feature "Priority support"

# מחזיר prod_AbCdEf...

# מחיר מנוי חודשי (₪49.90 לחודש)
npx @ching-payments/cli prices create \
  --product prod_AbCdEf \
  --amount 4990 \
  --type recurring \
  --interval month \
  --tax-mode inclusive

# שנתי עם 14 ימי trial
npx @ching-payments/cli prices create \
  --product prod_AbCdEf \
  --amount 49900 \
  --type recurring \
  --interval year \
  --trial-days 14
```

לתמחור חד-פעמי משתמשים ב-`--type one_time` בלי `--interval`. ההתייחסות המלאה ב-`references/cli-command-reference.md`.

יצירת מפתח API ו-webhook מהטרמינל (חלופה ללוח הבקרה בשלב 1). שני הסודות מודפסים פעם אחת בלבד - מעתיקים מיד:

```bash
# הנפקת מפתח API (לפי המצב הפעיל -> ck_test_ ב-test, ck_live_ ב-live).
# דורש התחברות בדפדפן (ching login); session של --with-key לא יכול ליצור מפתחות.
npx @ching-payments/cli api-keys create --name "Acme server key"

# רישום webhook במצב הנוכחי. מדפיס את סוד החתימה whsec_ פעם אחת.
npx @ching-payments/cli webhooks create \
  --url https://acme.com/webhooks/ching \
  --events charge.succeeded charge.failed

# עיון מאוחר יותר (סודות לעולם לא מוצגים שוב - רק תצוגה ממוסכת):
npx @ching-payments/cli api-keys list
npx @ching-payments/cli webhooks list
```

החלפת מצבים באמצע shell:

```bash
npx @ching-payments/cli use --test
npx @ching-payments/cli use proj_xyz --live
npx @ching-payments/cli prices list --json
```

כתיבה ב-Live מבקשת אישור. ב-CI מעבירים `--yes`.

ה-CLI לא כולל מאזין וובהוקים. להשתמש ב-ngrok או tunnel דומה כדי לחשוף endpoint מקומי בזמן פיתוח.

### שלב 3: אימות בקשות API מהשרת

כל קריאה הולכת ל-`https://api.ching.co.il/ching/v1/<resource>` עם `Authorization: Bearer <key>` ו-`Content-Type: application/json`. אין SDK עדיין; משתמשים ב-`fetch`/`axios`/`requests`.

עוזר ב-Node.js:

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

מבנה שגיאה (תמיד עם `success: false`):

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

אין עדיין idempotency keys; מבצעים dedupe של כתיבות בצד שלכם, באמצעות אילוץ DB או טבלת hashes של בקשות.

### שלב 4: חיוב חד-פעמי עם Checkout Sessions

בצד השרת, יוצרים session ומפנים את המשתמש ל-`url` שחוזר. העמוד ב-`secured.ching.co.il` מטפל בכרטיסי אשראי, ביט, Apple Pay, Google Pay, PayBox והעברה בנקאית.

```js
// POST /api/checkout
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    mode: 'single_price',
    price: 'price_AbCdEf',
    customer: 'cus_XyZ',
    success_url: 'https://app.example.com/billing/success?cs={CHECKOUT_SESSION_ID}',
    cancel_url: 'https://app.example.com/billing/cancel',
    create_document: true,
  }),
});
return Response.redirect(session.url, 303);
```

לעגלה שולחים `line_items: [{ name, description, image_url, amount_agorot, quantity, price?, product? }]` במקום `price`. אם שולחים גם `price` (מחזורי) וגם `line_items` יחד, זה **mixed checkout** - מנוי בתוספת פריטים חד-פעמיים באותה session (ראו למטה).

**פריטי שורה והנחות.** פריט שורה הוא ad-hoc כברירת מחדל - רק שם וסכום - ואין לו קישור למוצר/מחיר ב-CHING. לכן הנחה שמכוונת למוצר או מחיר ספציפי **לא** תחול על פריט שורה רגיל (רק הנחות ברמת ההזמנה חלות עליו). כדי שפריט שורה יהיה זכאי להנחה ממוקדת מוצר/מחיר, מציינים בו `price` (מזהה המחיר ב-CHING שהפריט מייצג - זה גם מאתר את המוצר ההורה) או `product` (מזהה מוצר). מזהה לא קיים נדחה עם `line_item_target_not_found`.

- **מכירת פריטים מקטלוג CHING** (למשל מחיר דמי-הקמה שיצרתם ב-CHING, או מוצרים חד-פעמיים שאתם רוצים להחיל עליהם הנחה): שלחו `price` (או `product`) בכל פריט שורה כדי שההנחות יחולו.
- **עגלות e-commerce טהורות** שה-SKU שלהן אינם מוצרי CHING: השאירו את `price`/`product` ריקים. אתם לא מחייבים על מוצרים שנוצרו ב-CHING, אז אין מה לקשר - הפריטים האלה פשוט לא זכאים להנחות ממוקדות מוצר/מחיר (הנחות ברמת ההזמנה עדיין חלות).

Sessions פגות תוקף 30 דקות אחרי יצירה. יוצרים אחת חדשה לכל ניסיון checkout. אסור לעשות שימוש חוזר ב-URL של session.

אחרי שהלקוח שילם, CHING שולח `charge.succeeded` לוובהוק שלכם (שלב 7). ההפניה ל-`success_url` היא ל-UX בלבד; אסור לתת הרשאה רק על בסיס ההפניה.

#### עדכון ו-upsert של לקוחות

כדי לעדכן לקוח קיים, שולחים `POST /customers/:id` עם השדות שרוצים לשנות בלבד (patch - שדות שלא נשלחו נשארים כמו שהם). מחזיר `404` אם ה-id לא קיים.

```js
await ching(`/customers/${customerId}`, {
  method: 'POST',
  body: JSON.stringify({ email: 'new@example.com', taxId: '514999874' }),
});
```

כדי ליצור-או-לעדכן בקריאה אחת, שולחים `POST /customers/upsert` עם `identifyBy` של `email`, `taxId` או `phone`. CHING מחפשת לקוח קיים במצב הנוכחי לפי השדה הזה; אם נמצא - מעדכנת אותו (patch), אחרת יוצרת לקוח חדש. התגובה כוללת `action: "created" | "updated"`. `name` נדרש רק כשנוצר לקוח חדש. מספרי טלפון מנורמלים ל-E.164 לפני ההשוואה, כך ש-`054-987-6543` מתאים ל-`+972549876543` שמור. אם יותר מלקוח אחד מתאים, מעודכן הלקוח שנוצר אחרון.

```js
const { data: customer, action } = await ching('/customers/upsert', {
  method: 'POST',
  body: JSON.stringify({
    identifyBy: 'email',           // 'email' | 'taxId' | 'phone'
    email,                          // מפתח ההתאמה - חייב להיות נוכח
    name: `${firstName} ${lastName}`,
    phone,
  }),
});
// action הוא 'created' או 'updated'; customer.id הוא ה-cus_* בכל מקרה
```

עדכון והתאמת upsert משדרים `customer.updated`; upsert שיוצר לקוח חדש משדר `customer.created`.

כדי למחוק לקוח, שולחים `DELETE /customers/:id`. זו **מחיקה רכה** (soft delete): הרשומה מסומנת כמחוקה אך לא נמחקת - כל החיובים, המסמכים והמנויים ממשיכים להצביע עליה כך שההיסטוריה הפיננסית נשמרת, וכרטיסים שמורים מנותקים. אם ללקוח יש מנוי במצב `active`, `trialing` או `past_due`, הקריאה מחזירה `409` (`CUSTOMER_HAS_ACTIVE_SUBSCRIPTION`); מבטלים קודם את המנוי ואז מוחקים. אחרי המחיקה הלקוח לא מופיע ב-`list`, לא מותאם ב-`upsert`, לא ניתן לעדכון, ו-`GET` מחזיר `{ id, object: "customer", deleted: true }`. משדר `customer.deleted`. הקריאה אידמפוטנטית.

```js
await ching(`/customers/${customerId}`, { method: 'DELETE' });
// -> { success: true, data: { id, object: 'customer', deleted: true } }
```

#### Mixed checkout (מנוי מחזורי + פריטים חד-פעמיים)

שולחים גם `price` וגם `line_items` כדי לחייב מנוי וגם פריטים חד-פעמיים באותה session - למשל תוכנית חודשית בתוספת דמי הקמה חד-פעמיים. אין שדה `mode`; שליחת שני המפתחות יחד בוחרת בענף הזה.

```js
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: customer.id,
    price: 'price_recurringMonthly',  // חייב להיות מחיר מחזורי
    line_items: [
      // `price` מקשר את הפריט למחיר ב-CHING (ולמוצר ההורה) כדי שהנחות
      // ממוקדות מוצר/מחיר יחולו. משמיטים אותו לפריטים ad-hoc.
      { name: 'דמי הקמה', amount_agorot: 4900, quantity: 1, price: 'price_setupFee' },
      { name: 'פגישת onboarding', amount_agorot: 12000, quantity: 1, price: 'price_onboarding' },
    ],
    success_url: 'https://app.example.com/billing/success?cs={CHECKOUT_SESSION_ID}',
    cancel_url: 'https://app.example.com/billing/cancel',
    create_document: true,
  }),
});
return Response.redirect(session.url, 303);
```

כללים והתנהגות:

- **ה-`price` חייב להיות מחזורי.** מחיר חד-פעמי יחד עם `line_items` נדחה עם `mixed_requires_recurring_price` (זו פשוט עגלה, השתמשו ב-`line_items` לבד).
- **`line_items` באותו מבנה כמו עגלה**: 1 עד 50 פריטים, `amount_agorot` חתום (שלילי = שורת הנחה), והסכום הכולל חייב להיות `>= 0` (אחרת `cart_total_invalid`).
- **כדי שהנחות יחולו על הפריטים החד-פעמיים, מציינים בכל פריט `price` (או `product`).** בלי זה הפריט הוא ad-hoc ורק הנחות ברמת ההזמנה חלות עליו (ראו "פריטי שורה והנחות" למעלה). לא נדרש ל-SKU של e-commerce שאינם מוצרי CHING.
- **`capture_method: 'manual'` נדחה** (`capture_method_not_supported_for_mixed`). mixed תמיד עובר דרך מסלול הכרטיס השמור כי חייבים לשמור כרטיס לחידושים; J5 hold לא יכול לאשר טוקן מחזורי. ארנקים מהירים מושבתים ב-sessions מסוג mixed מאותה סיבה.
- **תזמון החיוב תלוי ב-trial:**
  - בלי trial -> הלקוח מחויב `line_items_total + plan_first_period` מיד והמנוי מתחיל ב-`active`.
  - עם trial -> רק `line_items_total` מחויב עכשיו, המנוי מתחיל ב-`trialing`, והתקופה הראשונה של התוכנית מחויבת בסיום ה-trial (דרך cron החידוש הרגיל).
- ה-session הציבורי (`GET /checkout_sessions/:id/public`, בשימוש העמוד המתארח) חושף `billing_summary` ל-sessions מסוג mixed: `amount_due_now`, `one_time_amount_due_now`, `subscription_amount_due_now` (0 בזמן trial), `subscription_amount_due_later`, `trial_period_days`, `trial_end`.

אחרי שהלקוח שילם מתקבל `subscription.created` ואחריו `charge.succeeded` (או `charge.failed` אם החיוב המיידי נדחה, ואז המנוי נשאר `incomplete` וה-session נשאר פתוח לניסיון חוזר). מממשים הרשאה על בסיס הוובהוקים, לא ההפניה. ראו שלב 6 למחזור חיי המנוי ושלב 7 לאירועים.

#### חיוב מאוחר (J4J5 - capture_method=manual)

עבור חנויות מסחר אלקטרוני שבהן הסכום הסופי לא ידוע במעמד התשלום (סחורה לפי משקל, ייצור לפי הזמנה, אישור מלאי ידני) - שולחים `capture_method: 'manual'` ב-checkout session. CHING מאשרת חיוב בכרטיס (J5 hold של Grow) ומחכה לקריאת `POST /v1/charges/:id/capture` תוך 7 ימים - הכסף לא זז עד שתבצעו capture.

```js
const session = await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({
    customer: customer.id,
    line_items: [{ name: 'דג בס לק"ג', amount_agorot: 12000, quantity: 1 }],
    capture_method: 'manual',     // J5 hold, לא חיוב מיידי
    success_url: '...',
    cancel_url: '...',
  }),
});
```

אחרי שהלקוח שילם, מקבלים `charge.authorized` (לא `charge.succeeded`) ויש כ-7 ימים לפעול. אז:

```js
// המלאי אושר - מבצעים חיוב (מלא או חלקי; ההפרש משוחרר אוטומטית).
await ching(`/charges/${chargeId}/capture`, {
  method: 'POST',
  body: JSON.stringify({ amount: 13400 }),  // משמיטים לחיוב מלא
});
// charge.captured נורה; קבלות + חשבונית מס מופקות כאן.

// או, ההזמנה בוטלה - משחררים את ההזמנה.
await ching(`/charges/${chargeId}/cancel`, {
  method: 'POST',
  body: JSON.stringify({ cancellation_reason: 'requested_by_customer' }),
});
// charge.canceled נורה.
```

מגבלות חשובות:
- תקף רק למחירים חד-פעמיים ולעגלות עם כרטיס חדש. מחירים recurring נדחים; כרטיסים שמורים וארנקים מהירים (Apple Pay / Bit / Google Pay) מתעלמים מהדגל ונשארים automatic.
- ביטול משחרר את הרשומה ב-CHING מיידית, אבל הבנק של הלקוח עשוי לקחת עד **10 ימים** להסיר את ההזמנה ממסגרת האשראי הזמינה (חלון השחרור האוטומטי של Grow). הסבירו את זה ללקוח.
- ה-sweep היומי מבטל הזמנות שלא טופלו ב-`capturable_until` (כ-7 ימים) עם `cancellation_reason: 'expired'`.

### שלב 5: שמירת כרטיס בלי לחייב (Setup Sessions)

משתמשים ב-Setup Sessions כשצריך כרטיס בתיק לפני חיוב (טריאלים חינם, חיוב פוסט-פייד לפי שימוש, מנויים בלי חיוב מיידי).

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

Setup sessions פגים תוקף אחרי 24 שעות. בהצלחה, אמצעי התשלום החדש (`pm_*`) מצורף ללקוח ונורה `payment_method.attached`.

לרשימת כרטיסים שמורים של לקוח:

```js
const { data } = await ching(`/customers/cus_XyZ/payment_methods`);
// [{ id: 'pm_...', brand: 'visa', last4: '4242', exp_month: 12, exp_year: 2030 }, ...]
```

### שלב 6: מנויים (חיוב חוזר)

לאחר שיש ללקוח `pm_*`, אפשר ליצור מנוי מול מחיר recurring.

```js
const sub = await ching('/subscriptions', {
  method: 'POST',
  body: JSON.stringify({
    customer: 'cus_XyZ',
    price: 'price_recurringMonthly',
    payment_method: 'pm_AbCd',
  }),
});
// sub.status: 'trialing' | 'active' | 'incomplete'
```

מחזור החיים של הסטטוס:
- `trialing` (אם למחיר יש `trial_period_days`) -> `active` אחרי החיוב המוצלח הראשון
- `incomplete` אם החיוב הראשון נכשל; פג אוטומטית ל-`incomplete_expired` אחרי 23 שעות
- `active` -> `past_due` אם חיוב חוזר נכשל (ניסיונות חוזרים בימים 3, 7, 14) -> `canceled` אחרי הכישלון האחרון
- `subscription.trial_will_end` נורה 3 ימים לפני סוף ה-trial; להציג CTA "הוסף כרטיס"

ביטול:

```js
await ching(`/subscriptions/sub_AbCd/cancel`, { method: 'POST' });
```

הצגת החיוב הבא: `GET /subscriptions/:id` מחזיר הערכה של החיוב הבא כדי שתוכלו להציג את מחיר החידוש (כולל הנחה) בממשק שלכם:

```js
const { data: sub } = await ching('/subscriptions/sub_AbCd');
// next_charge_subtotal:        41300  // ברוטו לפני הנחות (אגורות)
// next_charge_discount_amount: 18054  // סך ההנחה
// next_charge_amount:          23246  // הסכום שיחויב בפועל (subtotal - discount)
// next_charge_discounts: [
//   { name: 'יריד מילואים', value_type: 'override', value: 19700,
//     duration: 'forever', charges_remaining: null, ends_at: null, amount_off: 18054 },
// ]
```

`next_charge_discounts` מפרט כל הנחה שמקטינה את החיוב הזה. `charges_remaining` מאוכלס רק עבור `n_charges` (כמה חיובים מוזלים נותרו, כולל הקרוב); `ends_at` רק עבור `until_date`; שניהם `null` עבור `once`/`forever`. המערך ריק כשאין הנחה, ומסיר הנחה ברגע שהיא הושלמה או פגה - כך שהוא תמיד משקף את החיוב הבא בפועל. שדות ה-`next_charge_*` קיימים ב-GET הבודד בלבד, לא ב-list או ב-create.

### שלב 6b: הנחות וקופונים (אופציונלי)

**כלל הנחה** (`disc_*`) מקטין את הסכום שהלקוח משלם. יוצרים אותו פעם אחת, ואז הוא חל **אוטומטית** (בכל פעם שנקנה מוצר/מחיר/הזמנה תואמים) או דרך **קוד** שהלקוח מקליד. כללים מכוונים להזמנה כולה (`order`), למוצרים ספציפיים (`products`) או למחירים ספציפיים (`prices`), ונושאים `duration` (`once`, `n_charges`, `until_date`, `forever`) שקובע כמה זמן הם ממשיכים להקטין את חיובי המנוי.

```js
// כלל "code": 25% הנחה על מחיר ספציפי, ל-3 החיובים הראשונים.
const disc = await ching('/discounts', {
  method: 'POST',
  body: JSON.stringify({
    name: 'Launch 25%',
    redemption: 'code',
    code: 'LAUNCH25',          // אותיות גדולות, [A-Z0-9_-], לא ייחודי
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

`value_type` הוא `percent` (basis points), `amount` (אגורות להפחתה; דורש `currency`), או `override` (אגורות כמחיר יחידה היעד; דורש `currency`, ו-`value_tax_mode` אופציונלי). אחרי היצירה ניתנים לעריכה רק `name`, `active`, חלון ה-active, מכסות ה-redemption, ו-`metadata` - value/type/target/duration מוקפאים כדי שהנחות שכבר הוחלו ישמרו על התנאים שלהן. ארכוב כלל עם `POST /discounts/:id/archive`; הנחות שכבר משויכות ממצות את ה-duration שלהן.

מחילים קוד בשלוש דרכים:

```js
// 1. מוחל מראש על checkout session מתארח (מוצג כצ'יפ שניתן להסרה).
await ching('/checkout_sessions', {
  method: 'POST',
  body: JSON.stringify({ customer, success_url, cancel_url, price, coupon_codes: ['LAUNCH25'] }),
});

// 2. על הדף המתארח עצמו (ציבורי, ללא auth): POST /checkout_sessions/:id/discount { code }
//    ו-DELETE /checkout_sessions/:id/discount/:code להסרה. ה-GET הציבורי מחזיר
//    תצוגה מקדימה חיה של ההנחה (discounts, discount_lines, total_discount_agorot).

// 3. ישירות ביצירת מנוי דרך ה-API:
await ching('/subscriptions', {
  method: 'POST',
  body: JSON.stringify({
    customer, price: 'price_recurringMonthly', payment_method,
    discounts: [{ code: 'LAUNCH25' }],   // או { discount: 'disc_...' }
  }),
});
```

כל כלל שמשויך הופך ל**הנחה מוחלת** (`di_*`, סטטוס `active` → `completed`/`canceled`). הוובהוקים הם `discount.created`/`updated`/`deleted` (מחזור חיי הכלל) ו-`discount.applied`/`discount.expired` (לכל מנוי). פירוט שדות מלא ב-`references/api-endpoints.md` ו-payloads ב-`references/webhook-events.md`.

### שלב 7: אימות וטיפול בוובהוקים

זה צעד האבטחה הקריטי ביותר. מאמתים כל וובהוק עם HMAC-SHA256 על גוף הבקשה הגולמי.

```js
import crypto from 'node:crypto';

export function verifyChingSignature(rawBody, header, secret) {
  const expected = crypto
    .createHmac('sha256', secret)
    .update(rawBody)
    .digest('hex');
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(header || '', 'hex');
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// Express handler. הגוף חייב להיות bytes גולמיים, לא אובייקט מנותח
app.post('/webhooks/ching',
  express.raw({ type: 'application/json' }),
  (req, res) => {
    const sig = req.header('Ching-Signature');
    if (!verifyChingSignature(req.body, sig, process.env.CHING_WEBHOOK_SECRET)) {
      return res.status(400).send('invalid signature');
    }
    const event = JSON.parse(req.body.toString('utf8'));
    handleEvent(event);
    res.json({ received: true });
  });
```

עוזר ב-Python קיים ב-`scripts/verify-webhook.py`.

סוגי אירועים שצריך לטפל בהם ב-SaaS בסיסי:

| אירוע | פעולה |
|-------|-------|
| `charge.succeeded` | מתן הרשאה, שליחת קבלה |
| `charge.failed` | יידוע הלקוח, רישום לאנליטיקת retry |
| `charge.authorized` | (J4J5 בלבד) סימון ההזמנה כ"כרטיס אושר, ממתין לחיוב". אין לבצע fulfilment - לא הועבר כסף. |
| `charge.captured` | (J4J5 בלבד) הכסף חויב; בצעו fulfilment. ב-payload יש `amount_captured` שעשוי להיות פחות מ-`amount` בחיוב חלקי. |
| `charge.canceled` | (J4J5 בלבד) ההזמנה שוחררה. שחררו מלאי שמור. `data.cancellation_reason` מסביר למה (`requested_by_customer` / `fraudulent` / `abandoned` / `expired`). |
| `payment_method.attached` | רענון UI של כרטיסים שמורים |
| `payment_method.detached` | רענון UI של כרטיסים שמורים |
| `subscription.created` | הקצאת חבילה |
| `subscription.updated` | סנכרון סטטוס (`active`, `past_due`, `canceled`) |
| `subscription.canceled` | ביטול הרשאה בסוף תקופה |
| `subscription.trial_will_end` | מייל "הוסף כרטיס" |
| `setup_session.failed` | UI של retry |
| `setup_session.expired` | UI של retry |
| `refund.created` | עדכון חשבונאות פנימית |
| `discount.applied` | (אם משתמשים בקופונים) הנחה שויכה למנוי; ה-payload הוא `applied_discount` |
| `discount.expired` | (אם משתמשים בקופונים) ה-duration של הנחת מנוי הסתיים; החיובים חוזרים למחיר מלא |

מבנה payload מלא וקטלוג האירועים המלא ב-`references/webhook-events.md`.

### שלב 8: החזרים

```js
await ching('/refunds', {
  method: 'POST',
  body: JSON.stringify({
    charge: 'ch_AbCd',
    amount_agorot: 4990,
    reason: 'requested_by_customer',
  }),
});
```

ההחזרים אסינכרוניים; הוובהוק `refund.created` נורה כשהבנק מאשר.

### שלב 9: פורטל לקוחות לניהול עצמי

שולחים לקוח מאומת לפורטל מאוחסן שבו הוא מנהל כרטיסים, מנויים ומוריד חשבוניות.

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

טוקני פורטל פגים אחרי כשעה. יוצרים מחדש בכל ביקור, לא לקאש את ה-URL.

### שלב 10: בדיקת האינטגרציה מקצה לקצה

1. עם API key של test, יוצרים customer ו-setup session.
2. פותחים את ה-URL שחוזר, משתמשים בזרימת sandbox ב-`secured.ching.co.il` כדי לצרף כרטיס.
3. מוודאים ש-`payment_method.attached` הגיע לוובהוק.
4. יוצרים מנוי מול מחיר recurring.
5. מוודאים `subscription.created` ו-`charge.succeeded` המיידי.
6. מבצעים החזר, מוודאים `refund.created`.
7. פותחים את ה-Billing Portal, מבטלים את המנוי, מוודאים `subscription.canceled`.

טאנלים לפיתוח: משתמשים ב-`ngrok http 3000` (או `cloudflared tunnel`) ומדביקים את ה-URL הציבורי בקונפיג הוובהוק בדשבורד. אסור להפנות וובהוקי production לטאנל.

## דוגמאות

### דוגמה 1: "להוסיף checkout של CHING לאפליקציית Next.js"

המשתמש אומר: "אני רוצה להוסיף חבילת Pro ב-₪49.90 לחודש דרך CHING checkout באפליקציית Next.js".

פעולות:
1. מבקשים מהמשתמש ליצור project, API key ו-webhook בדשבורד (שלב 1).
2. בלי להתקין כלום, משתמשים ב-`npx @ching-payments/cli` כדי ליצור את המוצר ומחיר recurring (שלב 2).
3. מוסיפים API route ב-`app/api/checkout/route.ts` שקורא ל-`POST /v1/checkout_sessions` ומבצע `Response.redirect` (שלב 4).
4. מוסיפים `app/api/webhooks/ching/route.ts` עם אימות HMAC כמו ב-`scripts/verify-webhook.py` (שלב 7).
5. ב-`subscription.created` קובעים את החבילה ב-DB.
6. ב-`subscription.canceled` קובעים downgrade ל-`current_period_end`.

תוצאה: זרימת מנוי עובדת, הקצאת הרשאות מונעת לחלוטין על ידי וובהוקים.

### דוגמה 2: "שמירת כרטיס בהרשמה, חיוב מאוחר יותר"

המשתמש אומר: "אני רוצה לאסוף כרטיס בהרשמה אבל לחייב לפי שימוש בסוף החודש".

פעולות:
1. יוצרים customer בזרימת ההרשמה: `POST /v1/customers`.
2. יוצרים Setup Session מיד אחרי, מפנים ל-`setup.url` (שלב 5).
3. ב-`payment_method.attached`, מסמנים את הלקוח כ"ניתן לחיוב" ב-DB.
4. בסוף החודש, מחשבים שימוש באגורות וקוראים ל-`POST /v1/charges` עם `customer`, `payment_method` (ה-`pm_*` השמור), `amount`, `description`.
5. ב-`charge.succeeded`, מסמנים את החשבונית כשולמה.

תוצאה: חיוב לפי שימוש בלי החזקת מספרי כרטיס.

### דוגמה 3: "החזר ללקוח שביטל תוך 14 יום"

המשתמש אומר: "לקוח רוצה כסף בחזרה. נרשם לפני 5 ימים ב-₪199".

פעולות:
1. מאתרים את ה-charge ID במערכת שלכם (או `GET /v1/charges?customer=cus_XyZ`).
2. מוציאים החזר: `POST /v1/refunds` עם `charge: 'ch_...'`, `reason: 'requested_by_customer'`.
3. מבטלים את המנוי: `POST /v1/subscriptions/sub_.../cancel`.
4. ב-`refund.created`, שולחים מייל אישור ומעדכנים חשבונאות.
5. ב-`subscription.canceled`, מבטלים הרשאה.

תוצאה: החזר וביטול נקיים בארבעה אירועי וובהוק.

### דוגמה 4: "חנות מסחר אלקטרוני עם סחורה לפי משקל (J4J5 manual capture)"

המשתמש אומר: "אנחנו מוכרים דגים לפי קילו; המחיר הסופי תלוי במה שנארוז בפועל. אני רוצה לאשר את הכרטיס במעמד התשלום ולחייב את הסכום האמיתי אחרי שנארוז".

פעולות:
1. יוצרים checkout session עם `capture_method: 'manual'` ו-`line_items` עם הערכת העגלה (שלב 4 - "חיוב מאוחר").
2. הלקוח משלם בעמוד המתארח; מקבלים `charge.authorized` (לא `charge.succeeded`). מסמנים את ההזמנה כ"כרטיס אושר, ממתין ל-fulfilment" ב-DB.
3. צוות ה-fulfilment שוקל ואורז את הסחורה.
4. קוראים ל-`POST /v1/charges/:id/capture` עם `amount` שווה לסכום האמיתי באגורות (או משמיטים לחיוב מלא). ההפרש משוחרר אוטומטית לכרטיס הלקוח.
5. ב-`charge.captured`, מסמנים את ההזמנה כשולמה ושולחים למשלוח. הקבלה וחשבונית המס מופקות אוטומטית במעמד ה-capture.
6. אם ההזמנה מבוטלת לפני capture, קוראים ל-`POST /v1/charges/:id/cancel` עם `cancellation_reason`. ההזמנה משוחררת מיידית ב-CHING; מזהירים את הלקוח שהבנק עשוי להמשיך להחזיק את הכסף עד 10 ימים.

תזכורת: חלון capture/cancel נסגר 7 ימים אחרי האישור (CHING מבטלת אוטומטית עם `cancellation_reason: 'expired'`).

תוצאה: זרימת authorize-then-capture בלי שכסף יזוז עד שה-fulfilment מאושר.

### דוגמה 5: "חיוב דמי הקמה יחד עם מנוי חדש (mixed checkout)"

המשתמש אומר: "כשמישהו נרשם לתוכנית של ₪99 לחודש אני רוצה לחייב גם דמי הקמה חד-פעמיים של ₪49 באותו checkout."

פעולות:
1. מוודאים שהלקוח קיים (`POST /customers`) ושהמחיר המחזורי נוצר (`price_*`, ₪99 לחודש).
2. יוצרים checkout session אחת ששולחת **גם** `price` (התוכנית המחזורית) **וגם** `line_items` (דמי ההקמה של ₪49) - זה mixed checkout (שלב 4 - "Mixed checkout"). מפנים ל-`session.url`.
3. הלקוח משלם בעמוד המתארח. בלי trial, CHING מחייבת ₪148 עכשיו (תקופת התוכנית הראשונה + דמי ההקמה) ומתקבל `subscription.created` (סטטוס `active`) ואז `charge.succeeded`.
4. ב-`subscription.created` מפעילים את התוכנית. דמי ההקמה לא דורשים טיפול נפרד - הם נכללו באותו חיוב ומסמך המס שלהם מונפק אוטומטית.
5. אם למחיר יש trial, רק דמי ההקמה (₪49) מחויבים עכשיו (סטטוס `trialing`); ה-₪99 הראשון של התוכנית מחויב בסיום ה-trial.

תוצאה: תוכנית + תשלום חד-פעמי נגבים בהפניה אחת, מימוש על בסיס הוובהוקים של המנוי והחיוב.

## משאבים מצורפים

### סקריפטים

- `scripts/verify-webhook.py` - מאמת את ה-Header `Ching-Signature` מול payload גולמי באמצעות HMAC-SHA256. שימושי לבדיקות נקודתיות או כיישום ייחוס. הרצה: `python3 scripts/verify-webhook.py --help`
- `scripts/agorot-converter.py` - ממיר בין שקלים לאגורות כדי למנוע באג off-by-100. הרצה: `python3 scripts/agorot-converter.py --help`

### מסמכי עזר

- `references/api-endpoints.md` - קטלוג endpoints מלא: כל ראוט REST ציבורי עם method, path, שדות חובה ורשות, ומוסכמות הקידומות של IDs. לעיון בעת בניית קריאת API חדשה או דיבוג של 4xx.
- `references/webhook-events.md` - כל סוגי האירועים של וובהוקים, מבנה payload, מחזור חיים וסמנטיקת retries. כולל אלגוריתם אימות HMAC המלא. לעיון בעת חיווט או דיבוג של handlers.
- `references/cli-command-reference.md` - כל פקודות `@ching-payments/cli` עם כל הדגלים ודוגמאות הרצה. לעיון בעת אוטומציה של פעולות קטלוג או בניית deploy automation.

## קישורי עזר

מקורות רשמיים לאימות ועדכון המידע בסקיל:

| מקור | URL | מה לבדוק |
|------|-----|----------|
| אתר השיווק של CHING | https://ching.co.il | מיצוב המוצר, חבילות מחיר |
| לוח הבקרה של הסוחר | https://app.ching.co.il | API keys, webhooks, מוצרים, לקוחות |
| בסיס ה-API | https://api.ching.co.il | בדיקת תקינות; ה-API הציבורי תחת `/ching/v1` (דורש `Authorization: Bearer ck_...`) |
| ה-CLI ב-npm | https://www.npmjs.com/package/@ching-payments/cli | גרסה אחרונה של ה-CLI, פקודת התקנה |
| כללי מע"מ ישראל (gov.il) | https://www.gov.il/he/departments/israel_tax_authority | שיעור מע"מ נוכחי, דרישות חשבונית |

## מלכודות נפוצות

- סכומים בבקשות API באגורות, לא בשקלים. ₪49.90 הם 4990. כפל ב-100 בקצה ה-API, חלוקה ב-100 בקצה ה-UI. בודקים על ידי round-trip של סכום ידוע דרך `scripts/agorot-converter.py`.
- חתימת הוובהוק היא HMAC-SHA256 על ה-bytes של גוף הבקשה הגולמי, לא על JSON שעבר parse ו-re-serialize. פריימוורקים שעושים auto-parse של JSON (Express, FastAPI, Next.js route handlers) ישברו את האימות בשקט. לוכדים את הגוף הגולמי לפני parsing.
- Checkout sessions פגים אחרי 30 דקות, setup sessions אחרי 24 שעות, טוקני billing portal אחרי כשעה. תמיד יוצרים session חדש לכל הפניה. אסור לקאש URL.
- ההפניה ל-`success_url` היא ל-UX בלבד. אירועי וובהוק הם הסיגנל היחיד האמין להצלחת תשלום. אסור לתת הרשאה רק על בסיס עמוד ההצלחה.
- מפתחות `ck_live_*` חסומים עד שהסוחר משלים KYC ב-Grow ומקשר זהות עסקית. פיתוח מקומי תמיד במצב test.
- אין עדיין idempotency keys. עוטפים כתיבות במפתח dedupe משלכם (לדוגמה `INSERT ... ON CONFLICT` על hash של בקשה) כדי לשרוד retries.
- ל-CLI אין פקודת `listen` להעברת וובהוקים. משתמשים ב-`ngrok` או `cloudflared tunnel` כדי לחשוף endpoint מקומי בזמן פיתוח.
- ניסיונות retry של מנויים רצים בימים 3, 7 ו-14 אחרי renewal שנכשל, ואז ביטול. בונים את מיילי ה-dunning סביב `subscription.updated` עם `status: 'past_due'`.

## פתרון בעיות

### שגיאה: 401 עם קוד `WRONG_CREDENTIALS`
סיבה: header `Authorization` חסר או שגוי, או שהמפתח הוחלף או נמחק בדשבורד.
פתרון: בודקים שה-header הוא בדיוק `Authorization: Bearer ck_test_<64hex>`. מאמתים שהמפתח עדיין קיים ב-https://app.ching.co.il/api-keys. מסובבים אם נחשף.

### שגיאה: 403 עם קוד `LIVE_KEY_INACTIVE`
סיבה: שימוש במפתח `ck_live_*` לפני שהסוחר השלים onboarding ב-Grow וקישור זהות עסקית.
פתרון: עוברים ל-`ck_test_*` לפיתוח, או מבקשים מהסוחר להשלים onboarding ב-https://app.ching.co.il/settings.

### שגיאה: וובהוק מחזיר "invalid signature"
סיבה: הגוף עבר parse (ו-re-serialize) לפני HMAC, או נעשה שימוש בסוד שגוי (test לעומת live, או endpoint לא נכון), או middleware נוסף שינה את ה-bytes.
פתרון: לוכדים את `req.body` כ-`Buffer`/`bytes` לפני parsing של JSON. משתמשים ב-`express.raw({ type: 'application/json' })` או במקבילה ב-FastAPI/Next.js. מאמתים שהסוד תואם ל-endpoint ולמצב.

### שגיאה: לקוח אומר "שילמתי אבל כלום לא קרה"
סיבה: הקוד נותן הרשאה על בסיס ההפניה ל-`success_url` (שהלקוח עלול לסגור) במקום על בסיס וובהוק `charge.succeeded`.
פתרון: מעבירים את כל ההפעלה ל-handler של הוובהוק. עמוד ההצלחה אמור רק להציג "תודה, בדקו אימייל".

### שגיאה: מנוי תקוע ב-`incomplete`
סיבה: החיוב הראשון נכשל; המנוי ממתין לתשלום מוצלח תוך 23 שעות.
פתרון: או מאפשרים לו לפוג ל-`incomplete_expired` ויוצרים חדש, או מבקשים מהלקוח לעדכן כרטיס דרך ה-Billing Portal (חיוב מוצלח שם מעביר ל-`active`).
