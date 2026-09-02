/**
 * Layered chibi RPG doll — base body + visible equipment (glamour), center stage.
 */
(function (global) {
  "use strict";

  const CLASS_PAL = {
    swordsman: { skin: "#ffd8b8", hair: "#5a3a1a", body: "#4a7fd4", trim: "#c9a227", eye: "#3a2a20" },
    mage: { skin: "#ffe8d0", hair: "#2a1848", body: "#6b4fd4", trim: "#b47aff", eye: "#2a1848" },
    archer: { skin: "#ffe0c8", hair: "#1a4038", body: "#2a9a78", trim: "#3ecfad", eye: "#1a3028" },
  };

  const RANK_SCALE = { novice: 0.9, intermediate: 1, veteran: 1.06, saint: 1.14 };

  const RARITY_GLOW = {
    common: "rgba(154,160,184,.35)",
    uncommon: "rgba(62,207,122,.55)",
    rare: "rgba(74,158,255,.65)",
    epic: "rgba(180,122,255,.75)",
    legendary: "rgba(255,210,122,.95)",
  };

  function weaponSvg(kind, tint) {
    const c = tint || "#c9a227";
    if (kind === "tech" || kind === "gear-weapon-tech") {
      return (
        '<svg viewBox="0 0 48 80" class="doll-gear-svg"><rect x="8" y="6" width="32" height="22" rx="3" fill="#222" stroke="' +
        c +
        '" stroke-width="2"/><rect x="10" y="28" width="28" height="4" rx="1" fill="' +
        c +
        '"/><rect x="22" y="32" width="4" height="38" rx="2" fill="' +
        c +
        '"/><rect x="16" y="66" width="16" height="6" rx="2" fill="#333" stroke="' +
        c +
        '"/></svg>'
      );
    }
    if (kind === "staff" || kind === "gear-weapon-staff") {
      return (
        '<svg viewBox="0 0 40 90" class="doll-gear-svg"><rect x="17" y="8" width="6" height="58" rx="3" fill="#8b6914"/><circle cx="20" cy="10" r="9" fill="' +
        c +
        '" opacity=".9"/><circle cx="20" cy="10" r="5" fill="#fff" opacity=".5"/></svg>'
      );
    }
    if (kind === "brush" || kind === "gear-weapon-brush") {
      return (
        '<svg viewBox="0 0 36 72" class="doll-gear-svg"><rect x="14" y="28" width="8" height="36" rx="2" fill="#8b6914"/><ellipse cx="18" cy="22" rx="12" ry="8" fill="' +
        c +
        '"/></svg>'
      );
    }
    if (kind === "bow" || kind === "gear-weapon-bow") {
      return (
        '<svg viewBox="0 0 56 72" class="doll-gear-svg"><path d="M40 8 C48 36 48 56 40 64" fill="none" stroke="' +
        c +
        '" stroke-width="4"/><line x1="40" y1="8" x2="40" y2="64" stroke="#8b6914" stroke-width="2"/></svg>'
      );
    }
    return (
      '<svg viewBox="0 0 48 88" class="doll-gear-svg"><linearGradient id="wg"><stop offset="0%" stop-color="#fff"/><stop offset="55%" stop-color="' +
      c +
      '"/><stop offset="100%" stop-color="#6a4e12"/></linearGradient><rect x="20" y="10" width="8" height="52" rx="2" fill="url(#wg)"/><rect x="14" y="58" width="20" height="8" rx="2" fill="' +
      c +
      '"/><polygon points="24,4 28,12 20,12" fill="#eee"/></svg>'
    );
  }

  function armorHtml(item) {
    const c = (item && item.tint) || "#5b6abf";
    const css = (item && item.css) || "";
    if (css.indexOf("cloak") >= 0 || css.indexOf("uniform") >= 0) {
      return '<div class="doll-armor-piece coat" style="--gear:' + c + '"></div>';
    }
    if (css.indexOf("apron") >= 0) {
      return '<div class="doll-armor-piece apron" style="--gear:' + c + '"></div>';
    }
    if (css.indexOf("vest") >= 0) {
      return '<div class="doll-armor-piece vest" style="--gear:' + c + '"></div>';
    }
    return '<div class="doll-armor-piece chest" style="--gear:' + c + '"></div>';
  }

  function cloakHtml(item) {
    const c = (item && item.tint) || "#3a2f8a";
    const r = (item && item.rarity) || "uncommon";
    return (
      '<div class="doll-cloak-piece rarity-' +
      r +
      '" style="--gear:' +
      c +
      ';--glow:' +
      (RARITY_GLOW[r] || RARITY_GLOW.common) +
      '"><span class="cloak-l"></span><span class="cloak-r"></span></div>'
    );
  }

  function accessoryHtml(item) {
    const c = (item && item.tint) || "#b4aee8";
    return '<div class="doll-acc-piece" style="--gear:' + c + '"><span class="gem"></span></div>';
  }

  function artifactHtml(item) {
    const c = (item && item.tint) || "#ffd27a";
    const r = (item && item.rarity) || "legendary";
    return (
      '<div class="doll-art-piece rarity-' +
      r +
      '" style="--gear:' +
      c +
      ';--glow:' +
      (RARITY_GLOW[r] || RARITY_GLOW.legendary) +
      '"></div>'
    );
  }

  function resolveWeaponKind(item) {
    if (!item) return "blade";
    const css = item.css || "";
    if (css.indexOf("tech") >= 0) return "tech";
    if (css.indexOf("staff") >= 0) return "staff";
    if (css.indexOf("brush") >= 0) return "brush";
    if (css.indexOf("bow") >= 0) return "bow";
    if ((item.item_id || "").indexOf("keyboard") >= 0) return "tech";
    if ((item.item_id || "").indexOf("stylus") >= 0) return "brush";
    return "blade";
  }

  function render(container, opts) {
    if (!container) return;
    const classId = (opts && opts.classId) || "swordsman";
    const rankId = (opts && opts.rankId) || "novice";
    const pal = CLASS_PAL[classId] || CLASS_PAL.swordsman;
    const scale = RANK_SCALE[rankId] || 1;
    const loadout = (opts && opts.loadout) || {};
    const wpn = loadout.weapon;
    const arm = loadout.armor;
    const acc = loadout.accessory;
    const art = loadout.artifact;
    const clk = loadout.cloak;

    const wTint = (wpn && wpn.tint) || pal.trim;
    const bodyTint = (arm && arm.tint) || pal.body;

    container.innerHTML =
      '<div class="rpg-doll class-' +
      classId +
      " rank-" +
      rankId +
      '" style="--skin:' +
      pal.skin +
      ";--hair:" +
      pal.hair +
      ";--body:" +
      bodyTint +
      ";--trim:" +
      pal.trim +
      ";--eye:" +
      pal.eye +
      ";--scale:" +
      scale +
      '">' +
      '<div class="doll-aura" aria-hidden="true"></div>' +
      '<div class="doll-cloak-slot">' +
      (clk ? cloakHtml(clk) : "") +
      "</div>" +
      '<div class="doll-body">' +
      '<div class="doll-head">' +
      '<div class="doll-hair"></div>' +
      '<div class="doll-face"><span class="eye l"></span><span class="eye r"></span><span class="mouth"></span></div>' +
      '<div class="doll-acc-slot">' +
      (acc ? accessoryHtml(acc) : "") +
      "</div>" +
      "</div>" +
      '<div class="doll-torso">' +
      armorHtml(arm) +
      '<div class="doll-arm arm-l"></div>' +
      '<div class="doll-arm arm-r">' +
      '<div class="doll-weapon-slot' +
      (wpn ? " has-gear" : "") +
      '">' +
      (wpn ? weaponSvg(resolveWeaponKind(wpn), wTint) : "") +
      "</div></div>" +
      "</div>" +
      '<div class="doll-legs"><span class="leg l"></span><span class="leg r"></span></div>' +
      "</div>" +
      '<div class="doll-art-slot">' +
      (art ? artifactHtml(art) : "") +
      "</div>" +
      '<div class="doll-shadow" aria-hidden="true"></div>' +
      "</div>";
  }

  global.CharacterDoll = { render, CLASS_PAL, RANK_SCALE };
})(typeof window !== "undefined" ? window : globalThis);
