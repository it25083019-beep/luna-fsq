# -*- coding: utf-8 -*-
"""Custom hue strip + sprite stage contrast."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_theme_js_custom_hue():
    js = (ROOT / "static" / "theme.js").read_text(encoding="utf-8")
    assert "applyCustomHue" in js
    assert "luna_theme_hue" in js
    assert 'id === "custom"' in js or 'saved === "custom"' in js
    print("OK theme.js custom hue")


def test_settings_has_rgb_strip():
    html = (ROOT / "static" / "app.html").read_text(encoding="utf-8")
    assert 'id="hueStrip"' in html
    assert 'id="hueStripMenu"' in html
    assert "hue-strip" in html
    assert "luna-stage::before" in html
    assert "--sprite-glow" in html
    print("OK settings RGB strip + sprite halo")


def test_appearance_schema_accepts_hue():
    from schemas import AppearancePrefsRequest

    req = AppearancePrefsRequest(theme_id="custom", hue=200)
    assert req.theme_id == "custom"
    assert req.hue == 200
    print("OK appearance hue schema")


if __name__ == "__main__":
    test_theme_js_custom_hue()
    test_settings_has_rgb_strip()
    test_appearance_schema_accepts_hue()
    print("ALL theme custom tests passed")
