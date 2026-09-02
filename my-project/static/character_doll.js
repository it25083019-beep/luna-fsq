/**
 * Chibi RPG hero on the base stage.
 *
 * The chibi art already includes the outfit and weapon, so glamour gear is
 * shown in the slots orbiting the character rather than stacked on top of it.
 * Only rank scale and a rarity aura are applied to the sprite itself.
 */
(function (global) {
  "use strict";

  const CLASSES = ["swordsman", "mage", "archer"];
  const RANKS = ["novice", "intermediate", "veteran", "saint"];
  const RANK_SCALE = { novice: 0.92, intermediate: 1, veteran: 1.07, saint: 1.14 };
  const RARITY_ORDER = ["legendary", "epic", "rare", "uncommon", "common"];

  function chibiPath(classId, rankId) {
    const cls = CLASSES.indexOf(classId) >= 0 ? classId : "swordsman";
    const rank = RANKS.indexOf(rankId) >= 0 ? rankId : "novice";
    return "/static/rpg/chibi/" + cls + "_" + rank + ".png";
  }

  function fallbackPath(classId, rankId) {
    const cls = CLASSES.indexOf(classId) >= 0 ? classId : "swordsman";
    const rank = RANKS.indexOf(rankId) >= 0 ? rankId : "novice";
    return "/static/rpg/characters/" + cls + "_" + rank + "_stand.png";
  }

  function bestRarity(loadout) {
    let best = null;
    Object.keys(loadout || {}).forEach((slot) => {
      const item = loadout[slot];
      if (!item || !item.rarity) return;
      const i = RARITY_ORDER.indexOf(item.rarity);
      if (i < 0) return;
      if (best === null || i < best) best = i;
    });
    return best === null ? "" : RARITY_ORDER[best];
  }

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function render(container, opts) {
    if (!container) return;
    const classId = (opts && opts.classId) || "swordsman";
    const rankId = (opts && opts.rankId) || "novice";
    const loadout = (opts && opts.loadout) || {};
    const scale = RANK_SCALE[rankId] || 1;
    const rarity = bestRarity(loadout);
    const src = chibiPath(classId, rankId);
    const alt = (opts && opts.alt) || "";

    container.innerHTML =
      '<div class="rpg-doll chibi class-' +
      esc(classId) +
      " rank-" +
      esc(rankId) +
      (rarity ? " aura-" + esc(rarity) : "") +
      '" style="--scale:' +
      scale +
      '">' +
      '<div class="doll-aura" aria-hidden="true"></div>' +
      '<img class="doll-sprite" src="' +
      esc(src) +
      '" alt="' +
      esc(alt) +
      '" draggable="false" decoding="async" />' +
      '<div class="doll-shadow" aria-hidden="true"></div>' +
      "</div>";

    const img = container.querySelector(".doll-sprite");
    if (img) {
      img.onerror = function () {
        img.onerror = null;
        img.src = fallbackPath(classId, rankId);
      };
    }
  }

  global.CharacterDoll = { render, chibiPath, fallbackPath, RANK_SCALE };
})(typeof window !== "undefined" ? window : globalThis);
