import re
from typing import Dict, Any, Optional

EXTERIORS = [
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred"
]

class MatchingService:
    """
    Parses, canonicalizes, and verifies skin names to prevent false positive matches
    between StatTrak, Souvenir, and vanilla skin exteriors.
    """

    @staticmethod
    def parse_market_hash_name(name: str) -> Dict[str, Any]:
        """
        Parses a CS2 market_hash_name into its core components.
        Example: 'StatTrak™ AK-47 | Redline (Field-Tested)'
        """
        clean_name = name.strip()
        is_stattrak = "StatTrak™" in clean_name or "StatTrak" in clean_name
        is_souvenir = clean_name.startswith("Souvenir ")

        # Remove StatTrak / Souvenir prefixes for component parsing
        core = clean_name
        if is_stattrak:
            core = core.replace("StatTrak™", "").replace("StatTrak", "").strip()
        if is_souvenir:
            core = core.replace("Souvenir", "").strip()

        # Extract Exterior if present in parenthesis
        exterior = None
        for ext in EXTERIORS:
            if f"({ext})" in core:
                exterior = ext
                core = core.replace(f"({ext})", "").strip()
                break

        # Extract weapon and skin name (format: 'Weapon | SkinName')
        weapon = None
        skin_name = None
        if "|" in core:
            parts = core.split("|", 1)
            weapon = parts[0].strip()
            skin_name = parts[1].strip()
        else:
            # e.g. Cases, Capsules, Music Kits
            skin_name = core.strip()

        return {
            "canonical_name": clean_name,
            "weapon": weapon,
            "skin_name": skin_name,
            "exterior": exterior,
            "is_stattrak": is_stattrak,
            "is_souvenir": is_souvenir
        }

    @staticmethod
    def is_weapon_or_knife(name: str) -> bool:
        """
        Determines if an item is an actual CS2 weapon skin, knife, or glove,
        excluding stickers, graffitis, patches, music kits, and pins.
        """
        if not name:
            return False
        clean = name.strip()
        lower = clean.lower()

        non_weapon_prefixes = (
            "souvenir ",
            "sticker |",
            "sealed graffiti |",
            "graffiti |",
            "patch |",
            "music kit |",
            "collectible |",
            "pin |",
            "charm |",
            "tournament pass",
            "storage unit"
        )
        if any(lower.startswith(p) for p in non_weapon_prefixes):
            return False

        # Standard CS2 weapon skins and knives always contain '|'
        return "|" in clean

    @staticmethod
    def are_strictly_identical(name_a: str, name_b: str) -> bool:
        """
        Ensures two item names are 100% equivalent without cross-matching StatTrak, Souvenir, or wears.
        """
        parsed_a = MatchingService.parse_market_hash_name(name_a)
        parsed_b = MatchingService.parse_market_hash_name(name_b)

        return (
            parsed_a["canonical_name"] == parsed_b["canonical_name"] and
            parsed_a["is_stattrak"] == parsed_b["is_stattrak"] and
            parsed_a["is_souvenir"] == parsed_b["is_souvenir"] and
            parsed_a["exterior"] == parsed_b["exterior"]
        )

matching_service = MatchingService()
