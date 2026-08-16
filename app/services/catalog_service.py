"""
CS2 Canonical Skin Catalog and 10-Variant Generator.
Defines base skins, popular liquid skins, and generates the 10 standard market variants:
5 standard wears (FN, MW, FT, WW, BS) + 5 StatTrak™ wears.
"""

from typing import List, Dict, Any, Optional

EXTERIOR_NAMES = [
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred"
]

EXTERIOR_SHORT = {
    "Factory New": "FN",
    "Minimal Wear": "MW",
    "Field-Tested": "FT",
    "Well-Worn": "WW",
    "Battle-Scarred": "BS"
}

# Curated list of high-liquidity, high-volume popular CS2 weapon skins across tiers
POPULAR_BASE_SKINS = [
    # AK-47
    "AK-47 | Redline",
    "AK-47 | Slate",
    "AK-47 | Frontside Misty",
    "AK-47 | Phantom Disruptor",
    "AK-47 | Legion of Anubis",
    "AK-47 | Ice Coaled",
    "AK-47 | Nightwish",
    "AK-47 | Cartel",
    "AK-47 | Point Disarray",
    "AK-47 | The Empress",
    # AWP
    "AWP | Asiimov",
    "AWP | Atheris",
    "AWP | Mortis",
    "AWP | Duality",
    "AWP | Neo-Noir",
    "AWP | Wildfire",
    "AWP | Hyper Beast",
    "AWP | Elite Build",
    "AWP | Fever Dream",
    # M4A4
    "M4A4 | The Emperor",
    "M4A4 | Desolate Space",
    "M4A4 | Spider Lily",
    "M4A4 | Neo-Noir",
    "M4A4 | Evil Daimyo",
    "M4A4 | 龍王 (Dragon King)",
    "M4A4 | Temukau",
    "M4A4 | In Living Color",
    # M4A1-S
    "M4A1-S | Decimator",
    "M4A1-S | Cyrex",
    "M4A1-S | Night Terror",
    "M4A1-S | Hyper Beast",
    "M4A1-S | Player Two",
    "M4A1-S | Printstream",
    "M4A1-S | Nightmare",
    "M4A1-S | Leaded Glass",
    # Desert Eagle
    "Desert Eagle | Mecha Industries",
    "Desert Eagle | Conspiracy",
    "Desert Eagle | Light Rail",
    "Desert Eagle | Trigger Discipline",
    "Desert Eagle | Code Red",
    "Desert Eagle | Ocean Drive",
    "Desert Eagle | Printstream",
    # USP-S
    "USP-S | Printstream",
    "USP-S | Cortex",
    "USP-S | Cyrex",
    "USP-S | The Traitor",
    "USP-S | Ticket to Hell",
    "USP-S | Monster Mashup",
    "USP-S | Guardian",
    # Glock-18
    "Glock-18 | Water Elemental",
    "Glock-18 | Vogue",
    "Glock-18 | Bullet Queen",
    "Glock-18 | Gamma Doppler",
    "Glock-18 | Clear Polymer",
    "Glock-18 | Snack Attack",
    # SMGs & Others
    "MP9 | Starlight Protector",
    "MP9 | Food Chain",
    "MP9 | Mount Fuji",
    "MAC-10 | Disco Tech",
    "MAC-10 | Ensnared",
    "Galil AR | Chromatic Aberration",
    "Galil AR | Rocket Pop",
    "FAMAS | Commemoration",
    "FAMAS | Mecha Industries",
    "P250 | See Ya Later",
    "P250 | Visions",
    "SSG 08 | Dragonfire",
    "SSG 08 | Turbo Peek"
]

# Dedicated curated list of proven high-liquidity profitable CS2 skins under €50 with high-retention cashout potential
PROVEN_PROFITABLE_SKINS = [
    # High-Retention Budget Play Skins (€1 - €20)
    "AK-47 | Slate (Field-Tested)",
    "M4A4 | Evil Daimyo (Field-Tested)",
    "Glock-18 | Water Elemental (Field-Tested)",
    "USP-S | Cortex (Field-Tested)",
    "AWP | Mortis (Field-Tested)",
    "AWP | Atheris (Field-Tested)",
    "M4A1-S | Night Terror (Field-Tested)",
    "Desert Eagle | Light Rail (Field-Tested)",
    "USP-S | Ticket to Hell (Field-Tested)",
    "AK-47 | Phantom Disruptor (Field-Tested)",
    "M4A4 | Spider Lily (Field-Tested)",
    "Desert Eagle | Conspiracy (Minimal Wear)",
    "AWP | Fever Dream (Field-Tested)",
    "AK-47 | Ice Coaled (Field-Tested)",
    "Glock-18 | Vogue (Field-Tested)",

    # High-Demand Mid-Tier Liquid Skins (€20 - €75)
    "AK-47 | Redline (Field-Tested)",
    "M4A1-S | Decimator (Field-Tested)",
    "M4A1-S | Cyrex (Field-Tested)",
    "AK-47 | Legion of Anubis (Field-Tested)",
    "AK-47 | Frontside Misty (Field-Tested)",
    "AWP | Neo-Noir (Field-Tested)",
    "AWP | Duality (Field-Tested)",
    "M4A4 | Neo-Noir (Field-Tested)",
    "USP-S | The Traitor (Field-Tested)",
    "Desert Eagle | Mecha Industries (Field-Tested)",
    "AK-47 | Cartel (Field-Tested)",
    "AWP | Hyper Beast (Field-Tested)",
    "AWP | Asiimov (Field-Tested)",
    "M4A4 | The Emperor (Field-Tested)",
    "AK-47 | The Empress (Field-Tested)"
]


class SkinCatalogService:
    """Manages CS2 weapon skin catalog and generates the 10 official market variants."""

    @staticmethod
    def clean_base_name(name: str) -> str:
        """
        Extracts the clean base weapon and skin name (e.g. 'AK-47 | Redline')
        stripping any exterior parentheses and StatTrak/Souvenir tags.
        """
        clean = name.strip()
        clean = clean.replace("StatTrak™", "").replace("StatTrak", "").replace("Souvenir", "").strip()

        for ext in EXTERIOR_NAMES:
            clean = clean.replace(f"({ext})", "").strip()

        return clean

    @classmethod
    def generate_10_variants(cls, base_name_or_variant: str) -> List[Dict[str, Any]]:
        """
        Generates the complete set of 10 official market hash names for a skin:
        - 5 Vanilla Wears (FN, MW, FT, WW, BS)
        - 5 StatTrak™ Wears (FN, MW, FT, WW, BS)
        """
        base = cls.clean_base_name(base_name_or_variant)
        if "|" not in base:
            return []

        parts = base.split("|", 1)
        weapon = parts[0].strip()
        skin_name = parts[1].strip()

        variants = []

        # 1-5: Vanilla Wears
        for wear in EXTERIOR_NAMES:
            hash_name = f"{base} ({wear})"
            variants.append({
                "market_hash_name": hash_name,
                "base_name": base,
                "weapon": weapon,
                "skin_name": skin_name,
                "exterior": wear,
                "exterior_short": EXTERIOR_SHORT[wear],
                "is_stattrak": False,
                "variant_index": len(variants) + 1
            })

        # 6-10: StatTrak™ Wears
        for wear in EXTERIOR_NAMES:
            hash_name = f"StatTrak™ {base} ({wear})"
            variants.append({
                "market_hash_name": hash_name,
                "base_name": base,
                "weapon": weapon,
                "skin_name": skin_name,
                "exterior": wear,
                "exterior_short": EXTERIOR_SHORT[wear],
                "is_stattrak": True,
                "variant_index": len(variants) + 1
            })

        return variants

    @classmethod
    def get_all_popular_variants(cls) -> List[str]:
        """Returns all official market hash names for the curated popular CS2 skins."""
        all_hash_names = []
        for base in POPULAR_BASE_SKINS:
            variants = cls.generate_10_variants(base)
            for v in variants:
                all_hash_names.append(v["market_hash_name"])
        return all_hash_names


catalog_service = SkinCatalogService()
