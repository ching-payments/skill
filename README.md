# CHING Payments Integration Skill

A Claude Skill that teaches your AI coding assistant how to integrate the [CHING](https://ching.co.il) payments API into a SaaS or web product. Covers checkout sessions, saved cards, subscriptions, refunds, the customer billing portal, and webhook verification, with the `@ching-payments/cli` for catalog scaffolding.

Works with Claude Code and Cursor. Triggers on requests like "integrate CHING", "add CHING checkout", "accept payments in Israel", or any of the documented Hebrew transliterations.

## Install (recommended)

Use the CHING CLI. It downloads the latest skill from this repo, detects which AI tools you have on your machine, and drops the files in the right place.

```bash
npx @ching-payments/cli skill install
```

The CLI will ask:

1. **Where to install:** globally (`~/.claude/skills/`, `~/.cursor/rules/`) so every project can use it, or just in the current project (`./.claude/skills/`, `./.cursor/rules/`) so it ships to teammates via git.
2. **Which tools to install for:** Claude Code, Cursor, or both. Pre-selects the ones detected on your machine.

### Non-interactive install (CI / scripts)

```bash
# Install globally for Claude Code only, overwrite if already present
npx @ching-payments/cli skill install --global --target claude --force

# Install in the current project for both Claude Code and Cursor
npx @ching-payments/cli skill install --project --target claude,cursor
```

| Flag | Effect |
|------|--------|
| `--global` | Install in `$HOME` (default for non-TTY). |
| `--project` | Install in the current working directory. |
| `--target <ids>` | Comma-separated subset of `claude`, `cursor`. Defaults to detected tools. |
| `--force` | Overwrite an existing install instead of erroring. |
| `--json` | Machine-readable output. |

### Update, list, remove

```bash
# Re-run install to pull the latest version
npx @ching-payments/cli skill install --force

# See where the skill is currently installed
npx @ching-payments/cli skill list

# Remove
npx @ching-payments/cli skill uninstall
```

After installing or updating, restart your AI tool (or open a new chat) to pick up the new skill.

## Manual install

If you'd rather not use the CLI, copy this folder by hand:

| Tool | Destination |
|------|-------------|
| Claude Code (global) | `~/.claude/skills/ching-payments-integration/` |
| Claude Code (project) | `<project>/.claude/skills/ching-payments-integration/` |
| Cursor (global) | `~/.cursor/rules/ching-payments.mdc` (re-emit the frontmatter; Cursor uses `description`/`globs`/`alwaysApply`, not Anthropic's keys) |

Then restart the tool.

## What's in the skill

```
ching-skill/
├── SKILL.md                                  Main instructions (~2700 words)
├── references/
│   ├── api-endpoints.md                      Full REST endpoint catalog
│   ├── webhook-events.md                     Event types, signature verification snippets
│   └── cli-command-reference.md              Every @ching-payments/cli command and flag
└── scripts/
    ├── verify-webhook.py                     Reference HMAC-SHA256 verifier
    └── agorot-converter.py                   Shekels <-> agorot converter and JSON payload auditor
```

## Requirements

- Node.js 18+ (for the CLI and for running webhook verification snippets)
- A CHING merchant account at [app.ching.co.il](https://app.ching.co.il) with a test API key
- For local webhook development: an HTTPS tunnel like `ngrok` or `cloudflared`

## License

MIT
