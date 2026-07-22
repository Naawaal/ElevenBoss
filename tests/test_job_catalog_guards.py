"""US-42.8 job catalog guards — every main.py job listed in catalog."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "discord_bot" / "main.py"
CATALOG = (
    ROOT
    / "specs"
    / "035-integrity-remainder"
    / "contracts"
    / "job-catalog.md"
)


def _jobs_from_main() -> list[str]:
    text = MAIN.read_text(encoding="utf-8")
    # self.scheduler.add_job(name, ...
    return re.findall(r"scheduler\.add_job\(\s*(\w+)", text)


def test_main_registers_expected_jobs():
    jobs = _jobs_from_main()
    assert "transfer_listing_expiry_job" in jobs
    assert "league_lifecycle_wake_job" in jobs
    assert "daily_recovery_job" in jobs
    assert len(jobs) >= 10


def test_catalog_lists_every_main_job():
    catalog = CATALOG.read_text(encoding="utf-8")
    missing = [j for j in _jobs_from_main() if j not in catalog]
    assert missing == [], f"jobs missing from catalog: {missing}"


def test_catalog_mentions_run_once_or_rpc_keys():
    catalog = CATALOG.read_text(encoding="utf-8")
    assert "_run_once" in catalog or "league_operation_runs" in catalog
    assert "expire_stale_transfer_listings" in catalog
