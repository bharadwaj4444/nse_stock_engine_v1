from pathlib import Path

from app.sources.nse_shareholding import (
    _extract_shareholding_snapshot,
    _extract_total_shares,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "icicibank_shareholding_2026q2.xml"
)


def test_icicibank_shareholding_fixture_has_expected_total():
    xml_bytes = FIXTURE.read_bytes()

    assert _extract_total_shares(xml_bytes) == 7_178_746_196


def test_icicibank_shareholding_categories_match_filing():
    snapshot = _extract_shareholding_snapshot(FIXTURE.read_bytes())

    assert snapshot["shareholding_pattern_shares"] == 7_178_746_196
    assert snapshot["total_shares"] == 7_178_746_196

    # No promoter-category fact was present in the inspected XML.
    assert snapshot["promoter_shares"] is None

    assert snapshot["public_shares"] == 7_178_746_196
    assert snapshot["domestic_institutions_shares"] == 2_999_120_893
    assert snapshot["foreign_institutions_shares"] == 3_621_025_268
    assert snapshot["non_institutions_shares"] == 542_835_672
    assert snapshot["governments_shares"] == 15_764_363


def test_icicibank_government_aggregate_matches_components():
    snapshot = _extract_shareholding_snapshot(FIXTURE.read_bytes())

    # government_shares is the overall government aggregate,
    # not the central-government component.
    assert snapshot["government_shares"] == 15_764_363
    assert snapshot["governments_shares"] == 15_764_363

    components_excluding_aggregate = (
        15_694_107  # Central government, verified from the XML
        + snapshot["government_state_shares"]
        + snapshot["government_promoted_companies_shares"]
    )

    assert components_excluding_aggregate == snapshot["governments_shares"]

