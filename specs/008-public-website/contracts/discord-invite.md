# Contract: Discord Invite Integration

**Feature**: `008-public-website`  
**Related**: [site-config.md](./site-config.md)

## Primary CTA behavior

| Control | Action |
|---------|--------|
| **Invite Bot** (button/link) | Navigate to Discord OAuth authorize URL (new tab preferred on desktop) |
| **Join Support** | Navigate to `supportInviteUrl` |
| `/invite` route | Redirect to the same OAuth URL as Invite Bot |

## OAuth requirements

| Param | Required value |
|-------|----------------|
| `client_id` | Public Discord Application Client ID |
| `scope` | `bot applications.commands` (space-separated, URL-encoded) |
| `permissions` | Integer string; default `8` for v1 |

## Security

- **Never** embed `DISCORD_TOKEN` or any secret in the invite URL, HTML, or client bundle.
- Client ID is public by design.
- Support invite must be a **community** invite, not a privileged admin webhook.

## Failure modes

| Case | Site behavior |
|------|----------------|
| Discord OAuth down | User sees Discord error; site still explains product |
| Missing `clientId` in config | Build-time or release checklist fails; do not ship empty `client_id=` |
| Placeholder support URL | Release checklist fails |

## Alignment with bot ops

Historical invite in ElevenBoss ops docs:

```text
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

Website v1 matches this pattern so new invites behave like existing ones. Post-v1: audit and reduce `permissions` if league setup still works.
