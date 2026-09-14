# -*- coding: utf-8 -*-
"""Printable 1-page learning CV + boss-clear journey from real evidence."""
from __future__ import annotations

import html
from typing import Any, Dict, List

from career_portfolio import build_career_portfolio
from journey_engine import get_curriculum, list_bosses


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _boss_label(boss_type: str) -> str:
    return {"weekly": "単元テスト", "monthly": "学期末", "career_final": "認定試験"}.get(boss_type or "", "試験")


def build_growth_export(state: Dict[str, Any]) -> Dict[str, Any]:
    pf = build_career_portfolio(state)
    name = state.get("user_display_name") or "学習者"
    j = ((state.get("rpg") or {}).get("journey") or {})
    log = list(j.get("completion_log") or [])
    log_sorted = sorted([x for x in log if isinstance(x, dict)], key=lambda x: str(x.get("at") or ""), reverse=True)
    try:
        bosses = list(list_bosses(state) or [])
    except Exception:
        bosses = []
    career_id = j.get("career_id") or pf.get("career_id") or ""
    cur = get_curriculum(career_id) if career_id else {}
    les_by = {x["id"]: x for x in (cur.get("lessons") or [])}
    journey_rows: List[Dict[str, Any]] = []
    for bid in j.get("boss_clears") or []:
        les = les_by.get(bid) or {}
        att = (j.get("boss_attempts") or {}).get(bid) or {}
        journey_rows.append(
            {
                "id": bid,
                "title_ja": les.get("title_ja") or bid,
                "boss_type": les.get("boss_type") or att.get("boss_type") or "",
                "score": att.get("score"),
                "passed": True,
                "updated_at": att.get("updated_at"),
            }
        )
    for b in bosses:
        if b.get("id") in {x["id"] for x in journey_rows}:
            continue
        if b.get("cleared") or b.get("passed"):
            journey_rows.append(
                {
                    "id": b.get("id"),
                    "title_ja": b.get("title_ja") or b.get("id"),
                    "boss_type": b.get("boss_type") or "",
                    "score": b.get("score"),
                    "passed": True,
                    "updated_at": b.get("updated_at"),
                }
            )
    return {
        "ok": True,
        "name": name,
        "portfolio": pf,
        "timeline": log_sorted[:20],
        "boss_journey": journey_rows[:16],
        "skills": pf.get("skills") or [],
        "self_pr": pf.get("self_pr") or [],
        "evidence": pf.get("evidence") or [],
        "exams": pf.get("exams") or [],
        "story_ja": pf.get("story_ja") or "",
    }


def render_export_html(state: Dict[str, Any]) -> str:
    data = build_growth_export(state)
    pf = data["portfolio"]
    skills = "".join(f"<li>{_esc(s.get('label_ja') or s.get('id'))}</li>" for s in data["skills"][:10])
    pr = "".join(f"<li>{_esc(x)}</li>" for x in data["self_pr"])
    ev = "".join(
        f"<div class='ev'><b>{_esc(x.get('title_ja'))}</b> · {int((x.get('score') or 0)*100)}%<p>{_esc(x.get('snippet'))}</p></div>"
        for x in data["evidence"][:8]
    )
    bosses = "".join(
        f"<li><span>{_esc(_boss_label(x.get('boss_type')))}</span> {_esc(x.get('title_ja'))}"
        f" — {('合格 ' + str(int((x.get('score') or 0)*100)) + '%') if x.get('score') is not None else 'クリア'}</li>"
        for x in data["boss_journey"]
    )
    tl = "".join(
        f"<li>{_esc(str(x.get('at') or '')[:10])} {_esc(x.get('title_ja'))} {_esc(x.get('detail'))}</li>"
        for x in data["timeline"][:12]
    )
    if not skills:
        skills = "<li>レッスンを提出するとスキルが残ります。</li>"
    if not bosses:
        bosses = "<li>ボスを倒すと、ここに攻略記が残ります。</li>"
    if not tl:
        tl = "<li>クエストをクリアすると年表が増えます。</li>"
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"/>
<title>LUNA 成長ポートフォリオ — {_esc(data['name'])}</title>
<style>
  :root {{ --ink:#1c2a2e; --muted:#5a6e68; --gold:#b8892d; --paper:#fbf6ea; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; font:15px/1.55 "Hiragino Sans","Yu Gothic",sans-serif; color:var(--ink); background:#e8e0d0; }}
  .sheet {{ max-width:820px; margin:18px auto; background:var(--paper); padding:28px 32px 36px; box-shadow:0 10px 30px rgba(0,0,0,.12); }}
  h1 {{ font-size:1.45rem; margin:0 0 .2rem }}
  h2 {{ font-size:1.05rem; margin:1.2rem 0 .4rem; border-bottom:2px solid var(--gold); padding-bottom:.2rem }}
  .sub {{ color:var(--muted); font-size:.85rem; margin:0 0 1rem }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 18px }}
  .stat {{ background:#fff; border-radius:10px; padding:.45rem .65rem }}
  .stat b {{ display:block; font-size:1.15rem }}
  ul {{ margin:.2rem 0; padding-left:1.15rem }}
  .ev {{ background:#fff; border-radius:10px; padding:.5rem .65rem; margin:.35rem 0 }}
  .ev p {{ margin:.25rem 0 0; font-size:.82rem; color:var(--muted) }}
  .tagline {{ font-size:.78rem; color:var(--muted); margin-top:1.2rem }}
  @media print {{
    body {{ background:#fff }}
    .sheet {{ box-shadow:none; margin:0; max-width:none }}
    .noprint {{ display:none }}
  }}
</style></head>
<body>
  <div class="sheet">
    <p class="noprint" style="text-align:right"><button onclick="window.print()">印刷 / PDF保存</button></p>
    <h1>{_esc(data['name'])} — 学習CV</h1>
    <p class="sub">{_esc(pf.get('career_title_ja') or '進路未選択')} ／ {_esc(pf.get('rank_ja') or '見習い')} ／ レッスン{int(pf.get('completed_count') or 0)} ・ 試験クリア{int(pf.get('boss_clears') or 0)}</p>
    <div class="grid">
      <div class="stat">レッスン<strong>{int(pf.get('completed_count') or 0)}</strong></div>
      <div class="stat">ボス<strong>{int(pf.get('boss_clears') or 0)}</strong></div>
      <div class="stat">スキル<strong>{len(data['skills'])}</strong></div>
      <div class="stat">提出物<strong>{len(data['evidence'])}</strong></div>
    </div>
    <p>{_esc(data['story_ja'])}</p>
    <h2>自己PR（データ根拠）</h2>
    <ul>{pr or '<li>提出物が増えるとここに文が育ちます。</li>'}</ul>
    <h2>スキル</h2>
    <ul>{skills}</ul>
    <h2>ミニ成果物</h2>
    {ev or '<p>課題提出が作品になります。</p>'}
    <h2>ボス攻略記</h2>
    <ul>{bosses}</ul>
    <h2>クエスト年表</h2>
    <ul>{tl}</ul>
    <p class="tagline">LUNA Future Skill Quest — 測れる成長だけを残した1枚。</p>
  </div>
</body></html>
"""
