# Quickstart: Rarity Potential Cap Integrity (`049`)

## Prerequisites

- Spec/plan/contracts understood; cite **US-42.2 / 42.7 / 42.9** on mutating PRs  
- Dev DB with `DATABASE_URL`; do **not** mutate production until dry-run review  
- Repo migrations through `087` applied before `088`

## 1. Unit / property tests (containment)

```powershell
pytest tests/test_potential_generation.py tests/test_rarity_potential_integrity.py -q
```

Expect: cap boundaries; Epic dynamic boost capped at 92; regen/youth never exceed rarity; `overall > cap` generation rejected; `CreatedPlayerCard` rejects illegal POT.

## 2. Apply migration 088 (dev)

```powershell
python scratch/apply_migration_088.py
# or project-standard apply pattern for 088_rarity_potential_guards.sql
psql $env:DATABASE_URL -f supabase/scripts/verify_required_schema.sql
```

Expect: `rarity_potential_cap` present; rewritten RPCs loaded; audit table + RLS; verify passes for new guards.

## 3. Python ↔ SQL parity

```powershell
pytest tests/test_rarity_potential_sql_parity.py -q
```

Expect: each rarity in `RARITY_POT_CAPS` matches `SELECT rarity_potential_cap(...)`.

## 4. Live definition audit (before trusting rewrite)

```sql
SELECT pg_get_functiondef('public.process_match_result(text,uuid[],integer,numeric[],integer[],uuid)'::regprocedure);
-- also: register_new_player, claim_daily_pack, process_youth_intake,
-- sign_youth_scout_prospect, process_daily_academy_growth,
-- allocate_skill_point, process_stat_drill, claim_evolution_reward, train_with_fodder
```

Confirm rarity appears in dynamic POT and ingress reject logic after 088.

## 5. Read-only inventory + dry-run (non-negotiable)

```powershell
python scripts/potential_cap_audit.py --out reports/potential_cap_dryrun.csv
# optional: --write-audit-dry-run --batch-id dryrun1
```

```sql
SELECT public.count_potential_integrity_anomalies();
```

Expect: report rows with category A/B/C and confidence labels. **Zero card/balance writes.**

Resolve all `MANUAL_REVIEW` before repair apply.

## 6. Repair on clone (idempotency)

```powershell
python scripts/potential_cap_audit.py --write-audit-dry-run --batch-id BATCH1
python scripts/potential_cap_repair.py --batch BATCH1          # dry print
python scripts/potential_cap_repair.py --batch BATCH1 --apply
python scripts/potential_cap_repair.py --batch BATCH1 --apply  # expect changed=0
python scripts/potential_cap_notify.py --batch BATCH1          # print DMs
# python scripts/potential_cap_notify.py --batch BATCH1 --send
```

**Do not apply 089 until** `count_potential_integrity_anomalies() = 0`.

## 7. Validate constraints (089) after anomaly = 0

```powershell
python scratch/apply_migration_089.py
```

```sql
-- must return 0
SELECT COUNT(*) AS anomalies
FROM public.player_cards
WHERE public.rarity_potential_cap(rarity) IS NULL
   OR potential > public.rarity_potential_cap(rarity)
   OR (base_potential IS NOT NULL AND base_potential > public.rarity_potential_cap(rarity))
   OR overall > potential;
```

Invalid write smoke: Epic POT 93 / Epic OVR 93 POT 92 → rejected by CHECK or ingress.

## 8. Full suite + Discord smoke

```powershell
pytest tests/ -q
```

Smoke: drill/allocate/evolution at Epic 92 cannot push past 92; youth/regen cards show POT ≤ rarity; registration/pack with illegal card fails clearly.

## 9. Production order (ops window)

1. Deploy prevention (bot + 088)  
2. Dry-run on prod snapshot / read-only  
3. Repair + refund  
4. Anomaly 0  
5. 089 VALIDATE  
6. Grouped manager DMs from audit (actual refunds only)  
7. Watch anomaly count after match / academy / regen / aging  

## 10. Changelog

Update `change_log.md`: rarity absolute POT caps enforced; Common academy prospects capped at 75; affected managers may see corrected OVR/POT and resource returns where invalid upgrades were reversed.
