# Contract: Site Config

**Feature**: `008-public-website`  
**Module**: `src/config/site.ts` (website repo)  
**Schema**: [data-model.md](../data-model.md)

## Invariants

1. `discord.scopes` **must** equal or include `["bot", "applications.commands"]` (order may vary; both required when building the URL).
2. `discord.clientId` and `discord.supportInviteUrl` **must** be non-placeholder strings before production deploy.
3. `contact.privacyEmail` **must** be a real mailbox before production deploy.
4. `features` **must** include the six required pillar ids listed in the data model.
5. `footer` **must** include links to `/privacy` and `/terms`.
6. No field may store a Discord **bot token**, Supabase **service role** key, or database URL.

## Invite URL construction

If `discord.inviteUrl` is set, use it as-is.

Else build:

```text
https://discord.com/api/oauth2/authorize
  ?client_id={clientId}
  &permissions={permissions}
  &scope={urlencode(scopes joined by space)}
```

Default `permissions`: `8`.

Helper: `src/lib/invite-url.ts` — pure function, unit-testable without Next.

## Get Started content (v1 default)

| order | title | body must mention |
|-------|-------|-------------------|
| 1 | Invite the bot | Invite CTA / `/invite` |
| 2 | Register your club | `/register` |
| 3 | Set your squad | `/squad` |
| 4 | Play a match | match / battle flow in plain language |
| 5 | Train & develop | `/development` |
| 6 | Claim daily & energy | `/store` (optional 6th) |

## Change control

Edits to copy/URLs = commit to website repo → Vercel auto-deploy. No CMS webhook.
