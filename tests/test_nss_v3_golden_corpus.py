# tests/test_nss_v3_golden_corpus.py
"""Phase 0 Golden Corpus — exact_parity sporting digests (SC-008/009)."""
from __future__ import annotations

from match_engine.calibration.run_corpus import run_corpus, write_baselines


def test_golden_corpus_exact_parity():
    write_baselines()
    failures = run_corpus()
    assert not failures, "\n".join(failures[:20])
