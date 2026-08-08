# Contract: Changelog Version Claim RPCs

**Feature**: `056-shelve-pvp-automation`  
**Supersedes**: `specs/055-vote-reminders-changelog/contracts/deployment_changelog_rpc.md` key semantics  
**Migration**: redefine in `108_shelve_pvp_and_version_changelog.sql` (keep function names from 107)

## Identity rule

```text
claim_key = latest version header from change_log.md   # e.g. "1.5.0"
```

**MUST NOT** include commit SHA, deploy ID, mtime, or file hash.

## 1. `claim_deployment_changelog(p_deployment_key TEXT, p_instance_id TEXT DEFAULT 'default')`

`p_deployment_key` is the **version string**.

### Outcomes

| status | When | Caller action |
|--------|------|----------------|
| `already_posted` | Stored key equals `p_deployment_key` AND `posted_at` is set | Silent return |
| `already_claimed` | Same key, claim &lt; 10 minutes old, not posted | Silent return |
| `claimed` | New version, or expired unposted claim | Post embed, then complete |

Body edits under the same `## [version]` do not change the key → no new claim.

## 2. `complete_deployment_changelog(...)`

Call **only after** successful Discord channel send.

Suggested signature (compatible with 107, commit optional metadata):

```text
complete_deployment_changelog(
  p_deployment_key TEXT,   -- version
  p_version TEXT,          -- same version
  p_commit TEXT,           -- optional ops metadata; ignored for future claims
  p_channel_id BIGINT
)
```

Writes `posted_at`, `version`, optional `commit`, `channel_id`. Future claims compare **version/key only**.

## 3. Python service contract (`deployment_changelog.py`)

```text
entry = parse_latest_changelog_entry(change_log.md)
key = entry.version                          # NOT f"{version}:{commit}"
claim(key)
if claimed:
  send embed (existing builder/channel resolution)
  on success: complete(key, version, optional_commit, channel_id)
  on failure: do not complete (retryable after claim TTL)
```

## 4. Test expectations

| Scenario | Posts? |
|----------|--------|
| Restart, same version, same commit | No |
| Restart, same version, different commit | No |
| Edit text under current version | No |
| New `## [X.Y.Z]` section | Exactly one |
| Two instances race on new version | Exactly one |
| Discord send fails after claim | Remains retryable; no `posted_at` |
