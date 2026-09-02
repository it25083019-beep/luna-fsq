/**
 * Chibi RPG hero — evolution sprite base + glamour gear overlays (game stage).
 */
(function (global) {
  "use strict";

  const RANK_SCALE = { novice: 1, intermediate: 1.04, veteran: 1.1, saint: 1.18 };

  const RARITY_GLOW = {
    common: "rgba(154,160,184,.35)",
    uncommon: "rgba(62,207,122,.55)",
    rare: "rgba(74,158,255,.65)",
    epic: "rgba(180,122,255,.75)",
    legendary: "rgba(255,210,122,.95)",
  };

  function spritePath(classId, rankId) {
    const cls = classId || "swordsman";
    const rank = rankId || "novice";
    return "/static/rpg/characters/" + cls + "_" + rank + "_stand.png";
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function weaponSvg(kind, tint) {
    const c = tint || "#c9a227";
    if (kind === "tech" || kind === "gear-weapon-tech") {
      return (
        '<svg viewBox="0 0 48 80" class="doll-gear-svg"><rect x="8" y="6" width="32" height="22" rx="3" fill="#222" stroke="' +
        c +
        '" stroke-width="2"/><rect x="22" y="32" width="4" height="38" rx="2" fill="' +
        c +
        '"/></svg>'
      );
    }
    if (kind === "staff" || kind === "gear-weapon-staff") {
      return (
        '<svg viewBox="0 0 40 90" class="doll-gear-svg"><rect x="17" y="8" width="6" height="58" rx="3" fill="#8b6914"/><circle cx="20" cy="10" r="9" fill="' +
        c +
        '"/></svg>'
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
        '" stroke-width="4"/></svg>'
      );
    }
    return (
      '<svg viewBox="0 0 48 88" class="doll-gear-svg"><rect x="20" y="10" width="8" height="52" rx="2" fill="' +
      c +
      '"/><polygon points="24,4 28,12 20,12" fill="#eee"/></svg>'
    );
  }

  function cloakHtml(item) {
    const c = (item && item.tint) || "#3a2f8a";
    const r = (item && item.rarity) || "uncommon";
    return (
      '<div class="doll-cloak-piece rarity-' +
      r +
      '" style="--gear:' +
      c +
      ";--glow:" +
      (RARITY_GLOW[r] || RARITY_GLOW.common) +
      '"><span class="cloak-l"></span><span class="cloak-r"></span></div>'
    );
  }

  function accessoryHtml(item) {
    const c = (item && item.tint) || "#b4aee8";
    const r = (item && item.rarity) || "rare";
    return (
      '<div class="doll-acc-piece rarity-' +
      r +
      '" style="--gear:' +
      c +
      '"><span class="gem"></span></div>'
    );
  }

  function artifactHtml(item) {
    const c = (item && item.tint) || "#ffd27a";
    const r = (item && item.rarity) || "legendary";
    return (
      '<div class="doll-art-piece rarity-' +
      r +
      '" style="--gear:' +
      c +
      ";--glow:" +
      (RARITY_GLOW[r] || RARITY_GLOW.legendary) +
      '"></div>'
    );
  }

  function armorTintStyle(item) {
    if (!item || !item.tint) return "";
    return "--armor-tint:" + item.tint + ";";
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
    const scale = RANK_SCALE[rankId] || 1;
    const loadout = (opts && opts.loadout) || {};
    const wpn = loadout.weapon;
    const arm = loadout.armor;
    const acc = loadout.accessory;
    const art = loadout.artifact;
    const clk = loadout.cloak;
    const spr = (opts && opts.sprite) || spritePath(classId, rankId);
    const wTint = (wpn && wpn.tint) || "#c9a227";
    const topRarity = [art, wpn, clk, arm, acc]
      .filter(Boolean)
      .map((x) => x.rarity)
      .sort((a, b) => {
        const order = ["legendary", "epic", "rare", "uncommon", "common"];
        return order.indexOf(a) - order.indexOf(b);
      })[0];

    container.innerHTML =
      '<div class="rpg-doll sprite-mode class-' +
      esc(classId) +
      " rank-" +
      esc(rankId) +
      (topRarity ? " gear-glow-" + esc(topRarity) : "") +
      '" style="--scale:' +
      scale +
      ";" +
      armorTintStyle(arm) +
      '">' +
      '<div class="doll-aura" aria-hidden="true"></div>' +
      '<div class="doll-cloak-slot">' +
      (clk ? cloakHtml(clk) : "") +
      "</div>" +
      '<div class="doll-sprite-wrap" style="' +
      armorTintStyle(arm) +
      '">' +
      '<img class="doll-sprite" src="' +
      esc(spr) +
      '" alt="" draggable="false" decoding="async" />' +
      (arm && arm.tint ? '<div class="doll-armor-tint" aria-hidden="true"></div>' : "") +
      '<div class="doll-acc-slot">' +
      (acc ? accessoryHtml(acc) : "") +
      "</div>" +
      '<div class="doll-weapon-slot' +
      (wpn ? " has-gear" : "") +
      '">' +
      (wpn ? weaponSvg(resolveWeaponKind(wpn), wTint) : "") +
      "</div>" +
      "</div>" +
      '<div class="doll-art-slot">' +
      (art ? artifactHtml(art) : "") +
      "</div>" +
      '<div class="doll-shadow" aria-hidden="true"></div>' +
      "</div>";
  }

  global.CharacterDoll = { render, spritePath, RANK_SCALE };
})(typeof window !== "undefined" ? window : globalThis);
