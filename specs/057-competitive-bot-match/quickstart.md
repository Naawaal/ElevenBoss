# Quickstart: Competitive Bot Match (057)

**Goal**: Validate flag-off baseline, then flag-on ET → pens → recovery → suspensions without economy regression.

## Prerequisites

- Migrations through **109** applied; `verify_required_schema.sql` green  
- Bot with NSS v3 bot path available (`match_engine_v3_bot` as today)  
- Test guild; `COMPETITIVE_MATCH_ENABLED` / `game_config.competitive_match_enabled` controllable  

## 1. Flag off (regression)

```text
competitive_match_enabled = false
```

1. Run `/battle bot` → completes at 90' as today.  
2. Confirm no ET banner, no pens, settlement unchanged.  
3. `pytest` economy/bot smoke green.

**Expected**: SC-001.

## 2. Extra time only (dev flag on)

Enable flag. Seed or force regulation draw (test harness / high-draw tactics).

**Expected**: ET banner → two 5' periods → if still level, pens (or stop here if Phase 1 build has pens behind secondary gate).

Fitness after 90' carries; fatigue higher than regulation.

## 3. Shootout

Force ET draw.

**Expected**: pens banner; emoji sequence; early stop; sudden death if 5–5; final `x–x (hp–ap pens)`; football score unchanged by pen goals.

## 4. Recovery

1. Start match; interrupt mid-ET or after 3 pens (kill process / call recovery).  
2. Restart bot.  

**Expected**: resumes correct phase; no duplicate kicks; no double XP/coins.

## 5. Suspensions

1. Force straight red / second yellow in competitive match.  
2. Confirm `player_suspensions` row.  
3. Attempt `/battle bot` with that card in XI → blocked.  
4. Complete another Bot Battle with eligible XI → remaining decrements; after serve, card allowed.

## 6. Presentation / rate limits

Observe stadium message count vs baseline Bot Battle.

**Expected**: no one-message-per-corner spam; shootout updates one message where practical.

## 7. Automated tests

```bash
pytest tests/test_competitive_extra_time.py \
       tests/test_penalty_shootout.py \
       tests/test_competitive_recovery.py \
       tests/test_player_suspensions.py \
       tests/test_competitive_economy_regression.py -q
```

## 8. Calibration (pre–default-on)

Batch seeded sims across strength bands; check draw/ET/pen rates and AI win distribution against plan research targets. Keep flag off in production until soak passes.

## Done when

- [ ] Flag off = baseline  
- [ ] Flag on = ET + pens + recovery + suspensions  
- [ ] Economy regression clean  
- [ ] Schema verify green  
- [ ] Stadium cadence acceptable  
