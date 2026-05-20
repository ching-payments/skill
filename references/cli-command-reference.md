# @ching-payments/cli Command Reference

Package: `@ching-payments/cli` (latest on npm). Invoke with `npx @ching-payments/cli <command>` or install globally and run `ching <command>`.

Requires Node.js >= 18.

Credentials are stored at `~/.ching/config.json` (mode 0o600).

## Global flags

Available on every command:

| Flag | Effect |
|------|--------|
| `--json` | Output JSON instead of human-friendly tables. Use in CI / scripts. |
| `--project <id>` | Override active project for this call. Accepts `proj_*` or numeric primary key. |
| `--live` | Force live mode for this call (overrides config). |
| `--test` | Force test mode for this call (overrides config). |
| `--yes` | Skip live-write confirmation prompt. Use in CI. |
| `-h, --help` | Show help. |
| `-v, --version` | Show CLI version. |

## Auth & session

### `login`

```bash
npx @ching-payments/cli login                # opens browser OAuth
npx @ching-payments/cli login --with-key     # paste an API key (CI-friendly)
```

Browser flow: opens `app.ching.co.il/cli/authorize`, captures the callback on a loopback port. If browser cannot open, prints the URL for manual paste. Defaults to test mode after login.

### `logout`

```bash
npx @ching-payments/cli logout
npx @ching-payments/cli logout --revoke      # also revoke the server-side session
```

`--revoke` only applies to browser-issued tokens.

### `whoami`

```bash
npx @ching-payments/cli whoami
npx @ching-payments/cli whoami --json
```

Prints user, project, mode, masked credential.

### `use [project]`

```bash
npx @ching-payments/cli use proj_AbCd
npx @ching-payments/cli use 5                # numeric project id
npx @ching-payments/cli use proj_AbCd --live
npx @ching-payments/cli use --test           # switch mode only
```

API-key sessions are project-scoped server-side, so this command only works with browser-token sessions.

### `open [page]`

```bash
npx @ching-payments/cli open                 # dashboard home
npx @ching-payments/cli open products
npx @ching-payments/cli open webhooks
npx @ching-payments/cli open api-keys
```

Supported pages: `dashboard`, `home`, `products`, `prices`, `customers`, `charges`, `refunds`, `subscriptions`, `documents`, `webhooks`, `api-keys`, `settings`, `billing`.

## Projects

A project is one merchant account. Most teams need only one for production and one for staging. The `projects` commands target the **account**, not a specific project, so they ignore `--project`, `--live`, and `--test`.

### `projects list`

```bash
npx @ching-payments/cli projects list
npx @ching-payments/cli projects list --json
```

Lists every project you have a role on. Marks the currently active project with a checkmark in the leftmost column. Output columns: ID (`proj_*`), Name, Business identity (numeric id or `-`), Created.

If you have no projects yet, the output prompts you to create one.

### `projects create`

```bash
# Interactive (TTY): prompts for the name
npx @ching-payments/cli projects create

# Fully scripted
npx @ching-payments/cli projects create --name "Acme Production"

# Attach an existing business identity at creation time
npx @ching-payments/cli projects create \
  --name "Acme Production" \
  --business-identity-id 42

# Force-switch to the new project even if you already have an active one
npx @ching-payments/cli projects create --name "Acme Staging" --switch

# Stay on your current project even when you had none active
npx @ching-payments/cli projects create --name "Acme Sandbox" --no-switch
```

| Flag | Required | Effect |
|------|----------|--------|
| `--name <name>` | Yes (non-interactive) | Project display name. |
| `--business-identity-id <id>` | No | Numeric id of an existing business identity to attach. Otherwise create one later in the dashboard. |
| `--switch` | No | After create, set the new project as active. |
| `--no-switch` | No | Do not switch, even if you currently have no active project. |

Default switch behaviour: if you have no active project, the new project becomes active. If you already have one, it stays. Override with `--switch` / `--no-switch`.

After create, the new project starts in test mode and has no API keys, webhooks, or business identity. Continue with:

```bash
# Create your first product in the new project
npx @ching-payments/cli products create --name "Pro Plan"

# Mint an API key and register a webhook (or use `open` to do it in the dashboard)
npx @ching-payments/cli api-keys create --name "Server key"
npx @ching-payments/cli webhooks create --url https://example.com/webhooks/ching --events charge.succeeded
```

### Note: API-key sessions cannot list or create projects

The `projects` commands require a browser-token session (`ching login` without `--with-key`). API keys are scoped to a single project server-side, so they have no view of the account's project list.

## Products

### `products list`

```bash
npx @ching-payments/cli products list
npx @ching-payments/cli products list --limit 10 --json
```

| Flag | Effect |
|------|--------|
| `--limit <n>` | Max products to return. |

### `products get <id>`

```bash
npx @ching-payments/cli products get prod_AbCd
```

### `products create`

```bash
npx @ching-payments/cli products create \
  --name "Pro Plan" \
  --description "Advanced features" \
  --feature "Unlimited reports|Up to 50 members" \
  --feature "Priority support" \
  --unlisted
```

| Flag | Required | Effect |
|------|----------|--------|
| `--name <name>` | Yes (non-interactive) | Product name. |
| `--description <text>` | No | Description. |
| `--feature <feature...>` | No | Repeatable. Format: `Title\|Subtitle` or `Title`. |
| `--unlisted` | No | Hide from public catalog. |

In a TTY, missing fields are prompted interactively.

### `products update <id>`

```bash
npx @ching-payments/cli products update prod_AbCd --name "Enterprise"
npx @ching-payments/cli products update prod_AbCd \
  --add-feature "Custom integrations|Zapier, n8n" \
  --add-feature "Dedicated CSM"
npx @ching-payments/cli products update prod_AbCd --clear-features
npx @ching-payments/cli products update prod_AbCd --no-unlisted
```

| Flag | Effect |
|------|--------|
| `--name <name>` | New name. |
| `--description <text>` | New description. |
| `--add-feature <feature...>` | Append features (preserves existing). |
| `--clear-features` | Remove all features. |
| `--unlisted` / `--no-unlisted` | Toggle visibility. |

At least one flag is required.

## Prices

### `prices list`

```bash
npx @ching-payments/cli prices list
npx @ching-payments/cli prices list --product prod_AbCd --json
```

| Flag | Effect |
|------|--------|
| `--product <id>` | Filter to a product. |
| `--limit <n>` | Max prices. |

Output formats `amount_agorot` as `₪X.XX` for readability.

### `prices get <id>`

```bash
npx @ching-payments/cli prices get price_AbCd
```

### `prices create`

```bash
# One-time price ₪49.90
npx @ching-payments/cli prices create \
  --product prod_AbCd \
  --amount 4990 \
  --type one_time \
  --tax-mode inclusive

# Monthly subscription ₪29.90 with 14-day trial
npx @ching-payments/cli prices create \
  --product prod_AbCd \
  --amount 2990 \
  --type recurring \
  --interval month \
  --trial-days 14

# Yearly subscription
npx @ching-payments/cli prices create \
  --product prod_AbCd \
  --amount 49900 \
  --type recurring \
  --interval year \
  --interval-count 1
```

| Flag | Required | Effect |
|------|----------|--------|
| `--product <id>` | Yes | Product to attach to. |
| `--amount <agorot>` | Yes | Unit amount in agorot (₪49.90 = 4990). |
| `--currency <code>` | No | Default `ils`. |
| `--type <type>` | Yes | `one_time` or `recurring`. |
| `--interval <interval>` | If recurring | `day`, `week`, `month`, `year`. |
| `--interval-count <n>` | No | Multiplier (default 1). |
| `--trial-days <n>` | No | Recurring only. |
| `--tax-mode <mode>` | No | `inclusive` or `exclusive`. |

## Customers

### `customers list`

```bash
npx @ching-payments/cli customers list
npx @ching-payments/cli customers list --limit 50 --json
```

### `customers get <id>`

```bash
npx @ching-payments/cli customers get cus_AbCd
```

### `customers create`

```bash
npx @ching-payments/cli customers create \
  --email "you@example.com" \
  --name "John Doe" \
  --phone "+972-50-1234567"
```

| Flag | Required | Effect |
|------|----------|--------|
| `--email <email>` | Yes | Customer email. |
| `--name <name>` | No | Display name. |
| `--phone <phone>` | No | E.164 phone. |

## Webhooks

Webhook endpoints are **mode-scoped**: a webhook created in test mode only receives test events, and `webhooks list` shows only the active mode's endpoints. Use `--live` / `--test` to target the other mode.

### `webhooks create`

```bash
# Variadic events
npx @ching-payments/cli webhooks create \
  --url https://example.com/webhooks/ching \
  --events charge.succeeded charge.failed

# Comma-separated events (equivalent)
npx @ching-payments/cli webhooks create \
  --url https://example.com/webhooks/ching \
  --events 'charge.succeeded,charge.failed'
```

| Flag | Required | Effect |
|------|----------|--------|
| `--url <url>` | Yes (non-interactive) | Endpoint URL. Must be `http(s)://`. |
| `--events <event...>` | Yes (non-interactive) | One or more event types. Repeatable or comma-separated; deduped. See `references/webhook-events.md` for the catalog. |

In a TTY, missing fields are prompted. The response prints the `whsec_<hex>` **signing secret exactly once** - it cannot be retrieved again. If lost, delete the endpoint and recreate it. Store the secret as `CHING_WEBHOOK_SECRET`.

### `webhooks list`

```bash
npx @ching-payments/cli webhooks list
npx @ching-payments/cli webhooks list --live --json
```

Columns: ID (numeric), URL, Events, Active, Created. Secrets are never shown.

### `webhooks delete <id>`

```bash
npx @ching-payments/cli webhooks delete 42
```

Takes the numeric id from `webhooks list`. CHING stops delivering events immediately.

## API keys

The active mode decides the kind of key minted: test mode -> `ck_test_*`, live mode -> `ck_live_*`. Live keys require a linked business identity and an active payment provider, otherwise the API returns `LIVE_KEY_PRECONDITIONS_NOT_MET`.

### `api-keys create`

```bash
npx @ching-payments/cli api-keys create --name "Acme server key"
npx @ching-payments/cli api-keys create --name "Acme live key" --live
```

| Flag | Required | Effect |
|------|----------|--------|
| `--name <name>` | No | Label for the key. Prompted in a TTY; defaults to "Test key"/"Live key". |

Prints the full key (`ck_test_`/`ck_live_<64 hex>`) **exactly once** - copy it immediately; only a masked preview is available afterwards.

**Requires a browser-token session** (`ching login` without `--with-key`): the key is tied to your user, so API-key auth has no user to attach and the command refuses with a message to run `ching login`. Listing, renaming, and deleting work with either sign-in method.

### `api-keys list`

```bash
npx @ching-payments/cli api-keys list
npx @ching-payments/cli api-keys list --json
```

Lists **both** test and live keys (this command is not mode-scoped). Columns: ID (numeric), Name, Key (masked preview), Mode, Active, Last used. Only the preview is shown - never the raw key.

### `api-keys rename <id>`

```bash
npx @ching-payments/cli api-keys rename 7 --name "Renamed key"
```

| Flag | Required | Effect |
|------|----------|--------|
| `--name <name>` | Yes (non-interactive) | New label. Prompted in a TTY. |

### `api-keys delete <id>`

```bash
npx @ching-payments/cli api-keys delete 7
```

Takes the numeric id from `api-keys list`. Any service still using the key starts failing immediately.

## Live-mode safety

All `create` and `update` commands prompt:

```
You are about to perform a LIVE write on <project>. Continue? (y/N)
```

Pass `--yes` to skip in CI. Read commands (`list`, `get`) never prompt.

## What the CLI does NOT do

- No `listen` / webhook forwarding (no built-in local tunnel for development webhooks). Use `ngrok` or `cloudflared tunnel`.
- No `trigger` to fabricate test events. Trigger them by calling the API in test mode (e.g., create a charge against a test card).
- No `init` / scaffold / template drop. Use this skill's body and bundled examples instead.

## Headers the CLI sends

```
Authorization: Bearer <token | api_key>
X-Project-Id: <numeric primary key>      # only when using browser token
X-Livemode: true | false                 # only when using browser token
Content-Type: application/json
User-Agent: ching-cli
```

API keys carry their mode in the prefix (`ck_test_` vs `ck_live_`), so `X-Livemode` is omitted for API-key auth.
