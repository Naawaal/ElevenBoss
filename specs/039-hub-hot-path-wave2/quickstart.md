# Quickstart: Hub Hot-Path Wave 2

```bash
# Contract tests
python -m pytest tests/test_hub_hot_path_wave2.py tests/test_config_cache.py -q

# Source await baseline (HP-4…HP-6)
python scratch/baseline_hub_roundtrips.py
```

Discord smoke: `/league hub`, `/squad`, `/profile` — confirm embeds match prior behavior; check logs for `perf.hub name=league_hub|squad|profile`.
