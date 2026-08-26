"""Generate chibi RPG class evolution SVG portraits (additive assets)."""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "static" / "rpg" / "characters"

PAL = {
    "swordsman": {
        "bg0": "#1b1540",
        "bg1": "#6b4a1e",
        "skin": "#ffd8b8",
        "hair": "#5a3a1a",
        "cloth": "#4a7fd4",
        "accent": "#c9a227",
        "metal": "#b8c8e8",
        "glow": "#fff6c8",
    },
    "archer": {
        "bg0": "#0f3a32",
        "bg1": "#2a8a78",
        "skin": "#ffd8b8",
        "hair": "#3d2810",
        "cloth": "#2d6b4a",
        "accent": "#6ecf8a",
        "metal": "#8fd4a8",
        "glow": "#e9fff9",
    },
    "mage": {
        "bg0": "#2a1860",
        "bg1": "#5b3db8",
        "skin": "#ffd8b8",
        "hair": "#3a2060",
        "cloth": "#4a3db8",
        "accent": "#b47aff",
        "metal": "#d4c4ff",
        "glow": "#f3eefe",
    },
}

RANK = {
    "novice": 0,
    "intermediate": 1,
    "veteran": 2,
    "saint": 3,
}


def _rank_tier(rank: str) -> int:
    return RANK.get(rank, 0)


def swordsman_weapon(t: int, p: dict) -> str:
    w = 4 + t * 2
    h = 36 + t * 14
    glow = ""
    if t >= 2:
        glow = f'<rect x="148" y="88" width="{w+6}" height="{h+8}" rx="3" fill="{p["glow"]}" opacity=".35"/>'
    if t >= 3:
        glow += f'<path d="M150 70 L158 58 L166 70 Z" fill="{p["glow"]}" opacity=".9"/>'
    blade = f'<linearGradient id="sw" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#fff"/><stop offset="55%" stop-color="{p["accent"]}"/><stop offset="100%" stop-color="#6a4e12"/></linearGradient>'
    return (
        blade
        + glow
        + f'<rect x="150" y="92" width="{w}" height="{h}" rx="2" fill="url(#sw)" stroke="#fff" stroke-width="1"/>'
        + f'<rect x="147" y="118" width="{w+6}" height="8" rx="2" fill="{p["accent"]}"/>'
    )


def archer_weapon(t: int, p: dict) -> str:
    stroke = 3 + t
    return (
        f'<path d="M148 130 Q118 95 88 118" fill="none" stroke="{p["accent"]}" stroke-width="{stroke}"/>'
        f'<line x1="88" y1="118" x2="148" y2="130" stroke="{p["metal"]}" stroke-width="2"/>'
        + (f'<circle cx="118" cy="108" r="14" fill="none" stroke="{p["glow"]}" stroke-width="2" opacity=".7"/>' if t >= 2 else "")
    )


def mage_weapon(t: int, p: dict) -> str:
    gem = 6 + t * 3
    staff_h = 50 + t * 12
    glow = f'<circle cx="154" cy="78" r="{gem+8}" fill="{p["glow"]}" opacity=".35"/>' if t >= 1 else ""
    if t >= 3:
        glow += f'<circle cx="154" cy="78" r="{gem+16}" fill="{p["accent"]}" opacity=".18"/>'
    return (
        glow
        + f'<rect x="151" y="82" width="6" height="{staff_h}" rx="3" fill="{p["metal"]}"/>'
        + f'<circle cx="154" cy="78" r="{gem}" fill="{p["accent"]}" stroke="#fff" stroke-width="1.5"/>'
    )


def body_block(cls: str, t: int, p: dict) -> str:
    cape = ""
    armor = ""
    if cls == "swordsman":
        if t >= 1:
            armor = f'<path d="M72 118 L128 118 L124 168 L76 168 Z" fill="{p["metal"]}" opacity=".55"/>'
        if t >= 2:
            cape = f'<path d="M58 108 Q100 92 142 108 L132 175 Q100 185 68 175 Z" fill="#2a2040" opacity=".75"/>'
            armor = f'<path d="M68 112 L132 112 L126 172 L74 172 Z" fill="{p["metal"]}" stroke="{p["accent"]}" stroke-width="2"/>'
        if t >= 3:
            cape = f'<path d="M52 100 Q100 78 148 100 L138 182 Q100 198 62 182 Z" fill="#fff" opacity=".22"/>'
            armor = f'<path d="M64 108 L136 108 L130 178 L70 178 Z" fill="#fff" opacity=".35" stroke="{p["glow"]}" stroke-width="2"/>'
    elif cls == "archer":
        if t >= 1:
            armor = f'<path d="M74 118 L126 118 L122 165 L78 165 Z" fill="{p["cloth"]}" stroke="{p["accent"]}" stroke-width="1.5"/>'
        if t >= 2:
            cape = f'<path d="M60 105 Q100 88 140 105 L130 172 Q100 182 70 172 Z" fill="#143830" opacity=".8"/>'
        if t >= 3:
            cape = f'<path d="M48 98 Q100 72 152 98 L140 186 Q100 202 60 186 Z" fill="#fff" opacity=".18"/>'
    else:
        if t >= 1:
            armor = f'<path d="M70 115 L130 115 L128 170 L72 170 Z" fill="{p["cloth"]}" stroke="{p["accent"]}" stroke-width="1.5"/>'
        if t >= 2:
            cape = f'<ellipse cx="100" cy="108" rx="46" ry="18" fill="#1a1040" opacity=".65"/>'
        if t >= 3:
            cape = f'<ellipse cx="100" cy="102" rx="52" ry="22" fill="#fff" opacity=".2"/>'

    head_extra = ""
    if cls == "mage":
        hat_w = 28 + t * 6
        head_extra = f'<polygon points="100,42 {100-hat_w/2},78 {100+hat_w/2},78" fill="{p["cloth"]}" stroke="{p["accent"]}" stroke-width="1.5"/>'
        if t >= 2:
            head_extra += f'<circle cx="100" cy="40" r="6" fill="{p["accent"]}"/>'
    elif cls == "archer" and t >= 1:
        head_extra = f'<path d="M72 62 Q100 48 128 62 L120 72 Q100 58 80 72 Z" fill="{p["cloth"]}"/>'

    wings = ""
    if t >= 3:
        wings = (
            f'<path d="M42 120 Q20 90 34 70 Q48 95 58 115 Z" fill="#fff" opacity=".55"/>'
            f'<path d="M158 120 Q180 90 166 70 Q152 95 142 115 Z" fill="#fff" opacity=".55"/>'
            f'<circle cx="100" cy="130" r="38" fill="{p["glow"]}" opacity=".12"/>'
        )

    return (
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="{p["bg1"]}"/><stop offset="100%" stop-color="{p["bg0"]}"/></linearGradient></defs>'
        f'<rect width="200" height="240" rx="18" fill="url(#bg)"/>'
        + wings
        + cape
        + f'<ellipse cx="100" cy="205" rx="42" ry="8" fill="#000" opacity=".22"/>'
        + f'<rect x="78" y="118" width="44" height="52" rx="12" fill="{p["cloth"]}"/>'
        + armor
        + f'<circle cx="100" cy="88" r="26" fill="{p["skin"]}"/>'
        + f'<ellipse cx="100" cy="72" rx="28" ry="22" fill="{p["hair"]}"/>'
        + f'<circle cx="90" cy="86" r="3" fill="#3a2a20"/><circle cx="110" cy="86" r="3" fill="#3a2a20"/>'
        + f'<path d="M94 98 Q100 103 106 98" fill="none" stroke="#c87858" stroke-width="2" stroke-linecap="round"/>'
        + head_extra
    )


def render(cls: str, rank: str) -> str:
    p = PAL[cls]
    t = _rank_tier(rank)
    weapon_fn = {"swordsman": swordsman_weapon, "archer": archer_weapon, "mage": mage_weapon}[cls]
    inner = body_block(cls, t, p) + weapon_fn(t, p)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 240" role="img" aria-label="{cls}-{rank}">\n'
        + inner
        + "\n</svg>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for cls in PAL:
        for rank in RANK:
            path = OUT / f"{cls}_{rank}.svg"
            path.write_text(render(cls, rank), encoding="utf-8")
            print("wrote", path.name)


if __name__ == "__main__":
    main()
