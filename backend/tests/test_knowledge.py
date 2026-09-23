"""Knowledge loading and retrieval (test-plan: test_knowledge.py).

Threshold-dependent tests set their own threshold (build-plan section 9.8)."""

import pytest


@pytest.mark.skip(reason="not implemented")
def test_K1_load_real_knowledge() -> None:
    """K1: >= 30 chunks, every chunk has machine and source."""


@pytest.mark.skip(reason="not implemented")
def test_K2_split_on_headings() -> None:
    """K2: 3 ## headings -> 3 chunks, frontmatter not in text."""


@pytest.mark.skip(reason="not implemented")
def test_K3_skip_without_frontmatter() -> None:
    """K3: file without frontmatter skipped, no crash."""


@pytest.mark.skip(reason="not implemented")
def test_K4_private_missing_ok() -> None:
    """K4: private/ missing -> loads fine."""


@pytest.mark.skip(reason="not implemented")
def test_K5_retrieve_sd_card() -> None:
    """K5: "what size SD card" (3d-printer) -> top heading mentions SD card."""


@pytest.mark.skip(reason="not implemented")
def test_K6_retrieve_pvc_banned() -> None:
    """K6: "can I cut PVC" (laser-cutter) -> top chunk is banned materials."""


@pytest.mark.skip(reason="not implemented")
def test_K7_machine_boost_ranks_first() -> None:
    """K7: equally similar chunks -> device machine ranks first."""


@pytest.mark.skip(reason="not implemented")
def test_K8_unrelated_not_confident() -> None:
    """K8: "best pizza" -> is_confident False."""


@pytest.mark.skip(reason="not implemented")
def test_K9_top_k_sorted() -> None:
    """K9: top_k 3 -> at most 3 results, sorted by score desc."""
