import pytest
from app.services.matching_service import matching_service

def test_exact_vanilla_skin_parsing():
    parsed = matching_service.parse_market_hash_name("AK-47 | Redline (Field-Tested)")
    assert parsed["canonical_name"] == "AK-47 | Redline (Field-Tested)"
    assert parsed["weapon"] == "AK-47"
    assert parsed["skin_name"] == "Redline"
    assert parsed["exterior"] == "Field-Tested"
    assert parsed["is_stattrak"] is False
    assert parsed["is_souvenir"] is False

def test_stattrak_skin_parsing():
    parsed = matching_service.parse_market_hash_name("StatTrak™ AK-47 | Redline (Field-Tested)")
    assert parsed["weapon"] == "AK-47"
    assert parsed["skin_name"] == "Redline"
    assert parsed["exterior"] == "Field-Tested"
    assert parsed["is_stattrak"] is True
    assert parsed["is_souvenir"] is False

def test_souvenir_skin_parsing():
    parsed = matching_service.parse_market_hash_name("Souvenir Desert Eagle | Mud-Spec (Field-Tested)")
    assert parsed["weapon"] == "Desert Eagle"
    assert parsed["skin_name"] == "Mud-Spec"
    assert parsed["exterior"] == "Field-Tested"
    assert parsed["is_stattrak"] is False
    assert parsed["is_souvenir"] is True

def test_stattrak_never_matches_normal():
    # Crucial requirement: StatTrak must NEVER match normal
    assert not matching_service.are_strictly_identical(
        "AK-47 | Redline (Field-Tested)",
        "StatTrak™ AK-47 | Redline (Field-Tested)"
    )

def test_souvenir_never_matches_normal():
    # Souvenir must NEVER match normal
    assert not matching_service.are_strictly_identical(
        "Desert Eagle | Mud-Spec (Field-Tested)",
        "Souvenir Desert Eagle | Mud-Spec (Field-Tested)"
    )

def test_different_wears_never_match():
    # Factory New vs Field-Tested
    assert not matching_service.are_strictly_identical(
        "AK-47 | Redline (Factory New)",
        "AK-47 | Redline (Field-Tested)"
    )
    # Minimal Wear vs Battle-Scarred
    assert not matching_service.are_strictly_identical(
        "AWP | Asiimov (Minimal Wear)",
        "AWP | Asiimov (Battle-Scarred)"
    )

def test_identical_names_match():
    assert matching_service.are_strictly_identical(
        "M4A1-S | Printstream (Field-Tested)",
        "M4A1-S | Printstream (Field-Tested)"
    )
