# Interface Contract: Deployment Changelog RPCs & Service

**Superseded key semantics (Feature 056)**: `p_deployment_key` is now the **version string only** (e.g. `1.4.0`), not `<version>:<commit>`. See `specs/056-shelve-pvp-automation/contracts/changelog-version-rpc.md`.

## 1. RPC: `claim_deployment_changelog`

**Signature**: `public.claim_deployment_changelog(p_deployment_key TEXT, p_instance_id TEXT)`

**Purpose**: Locks the `game_config` row for `last_changelog_deployment` and attempts to claim permission to post the changelog for `p_deployment_key`.

### Input Parameters
| Parameter | Type | Default | Description |
|---|---|---|---|
| `p_deployment_key` | `TEXT` | Required | Unique key string formatted as `<version>:<commit>` |
| `p_instance_id` | `TEXT` | `'default'` | Identifier of the bot instance claiming the release |

### Output JSON Format
```json
{
  "status": "claimed",
  "deployment_key": "1.4.0:ea590ab"
}
```
Possible `status` values:
- `"claimed"`: Claim granted, instance should post changelog.
- `"already_posted"`: Changelog was already posted for this deployment key.
- `"already_claimed"`: Another instance holds an active claim (< 10 min old).

---

## 2. RPC: `complete_deployment_changelog`

**Signature**: `public.complete_deployment_changelog(p_deployment_key TEXT, p_version TEXT, p_commit TEXT, p_channel_id BIGINT)`

**Purpose**: Marks the deployment changelog post as completed.

### Input Parameters
| Parameter | Type | Description |
|---|---|---|
| `p_deployment_key` | `TEXT` | Unique key string formatted as `<version>:<commit>` |
| `p_version` | `TEXT` | Version string (e.g. `"1.4.0"`) |
| `p_commit` | `TEXT` | Short commit hash (e.g. `"ea590ab"`) |
| `p_channel_id` | `BIGINT` | ID of Discord channel where posted |

### Output JSON Format
```json
{
  "status": "completed",
  "deployment_key": "1.4.0:ea590ab"
}
```
