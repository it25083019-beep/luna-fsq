# -*- coding: utf-8 -*-
"""Printable learning CV styled after the personal IT portfolio (glass / dark / hero)."""
from __future__ import annotations

import html
from typing import Any, Dict, List

from career_portfolio import build_career_portfolio
from journey_engine import get_curriculum, list_bosses


SUPPORT_EMAIL = "it25083019@tsb-yyg.ac.jp"


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _boss_label(boss_type: str) -> str:
    return {"weekly": "単元テスト", "monthly": "学期末", "career_final": "認定試験"}.get(boss_type or "", "試験")


def _initial(name: str) -> str:
    raw = (name or "L").strip()
    if not raw:
        return "L"
    ch = raw[0]
    return ch.upper() if "A" <= ch.upper() <= "Z" else ch


def _skill_icon(label: str, idx: int) -> str:
    icons = ["☕", "🗄️", "🎨", "☁", "🔒", "💼", "⚔", "📚", "🧩", "🛠"]
    key = (label or "").lower()
    if "java" in key or "code" in key or "program" in key:
        return "☕"
    if "data" in key or "sql" in key or "db" in key:
        return "🗄️"
    if "design" in key or "ui" in key or "web" in key:
        return "🎨"
    if "aws" in key or "cloud" in key:
        return "☁"
    if "security" in key or "安全" in key:
        return "🔒"
    return icons[idx % len(icons)]


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
    sprite = ""
    class_ja = ""
    level = int(state.get("current_level") or 1)
    try:
        from journey_engine import journey_status

        st = journey_status(state)
        ap = st.get("appearance") or {}
        sprite = ap.get("evolution_sprite") or ap.get("sprite") or ""
        class_ja = st.get("class_ja") or ""
        level = int(st.get("level") or level)
    except Exception:
        pass
    return {
        "ok": True,
        "name": name,
        "initial": _initial(str(name)),
        "level": level,
        "class_ja": class_ja,
        "sprite": sprite,
        "portfolio": pf,
        "timeline": log_sorted[:20],
        "boss_journey": journey_rows[:16],
        "skills": pf.get("skills") or [],
        "self_pr": pf.get("self_pr") or [],
        "evidence": pf.get("evidence") or [],
        "exams": pf.get("exams") or [],
        "story_ja": pf.get("story_ja") or "",
    }


_SITE_CSS = """
:root{
  --bg:#070b18;--bg-2:#10132a;--ink:#f8fbff;--muted:#c7d2ea;
  --cyan:#35e3ff;--violet:#a78bfa;--orange:#ff9f43;--pink:#ff5fa2;--green:#63f5b4;
  --glass:rgba(255,255,255,.075);--shadow:0 28px 80px rgba(0,0,0,.38);--radius:30px;--max:1100px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;min-height:100vh;color:var(--ink);
  background:
    radial-gradient(circle at 18% 8%, rgba(255,95,162,.17), transparent 26%),
    radial-gradient(circle at 85% 12%, rgba(53,227,255,.17), transparent 28%),
    radial-gradient(circle at 60% 85%, rgba(255,159,67,.12), transparent 32%),
    linear-gradient(180deg,#080b19 0%,#10132a 42%,#070b18 100%);
  font-family:"Noto Sans JP","Inter",system-ui,sans-serif;line-height:1.72;
}
body::before{
  content:"";position:fixed;inset:0;z-index:-3;pointer-events:none;
  background:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);
  background-size:42px 42px;
  mask-image:linear-gradient(to bottom,rgba(0,0,0,.78),transparent 78%);
}
a{color:inherit;text-decoration:none}
img{max-width:100%;display:block}
.container{width:min(var(--max),calc(100% - 36px));margin:0 auto}
.orbs{position:fixed;inset:0;pointer-events:none;z-index:-1;overflow:hidden}
.orb{position:absolute;border-radius:50%;filter:blur(40px);opacity:.55}
.orb-a{width:280px;height:280px;left:-40px;top:8%;background:rgba(53,227,255,.28)}
.orb-b{width:240px;height:240px;right:-30px;top:18%;background:rgba(167,139,250,.32)}
.orb-c{width:300px;height:300px;left:30%;bottom:-80px;background:rgba(255,159,67,.18)}
.site-header{position:sticky;top:0;z-index:50;background:rgba(8,16,29,.55);backdrop-filter:blur(18px);border-bottom:1px solid rgba(255,255,255,.08)}
.nav{min-height:68px;display:flex;justify-content:space-between;align-items:center;gap:16px}
.logo{display:inline-flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.1em}
.logo-mark{
  width:40px;height:40px;border-radius:14px;display:grid;place-items:center;color:#061020;font-weight:900;
  background:conic-gradient(from 180deg,var(--cyan),var(--violet),var(--orange),var(--cyan));
  box-shadow:0 12px 28px rgba(53,227,255,.26);
}
.nav-links{display:flex;gap:18px;font-size:.82rem;color:#c7d2ea}
.nav-cta,.btn{
  display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:.65rem 1.1rem;
  font-weight:800;font-size:.82rem;border:1px solid rgba(255,255,255,.14);cursor:pointer;
}
.btn.primary,.nav-cta{background:linear-gradient(135deg,var(--cyan),var(--violet));color:#061020}
.btn.secondary{background:rgba(255,255,255,.08)}
.hero{padding:72px 0 56px}
.hero-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:36px;align-items:center}
.eyebrow{
  display:inline-flex;align-items:center;gap:8px;padding:7px 12px;border-radius:999px;
  background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);font-size:.78rem;font-weight:700;
}
.live-dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 0 0 rgba(99,245,180,.7);animation:pulse 1.8s ease-out infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(99,245,180,.7)}70%{box-shadow:0 0 0 10px transparent}}
.hero-name{
  margin:16px 0 8px;font-size:clamp(2.1rem,6vw,4.4rem);line-height:1.05;letter-spacing:-.04em;
  background:linear-gradient(92deg,#fff 6%,var(--cyan) 28%,var(--violet) 52%,var(--orange) 78%,#fff);
  background-size:220% auto;-webkit-background-clip:text;background-clip:text;color:transparent;
  animation:shine 8s linear infinite;
}
@keyframes shine{to{background-position:220% center}}
.hero-title-en{margin:0 0 14px;letter-spacing:.18em;text-transform:uppercase;color:#9fb6d6;font-size:.95rem;font-weight:700}
.hero p{color:#c8d6ea;margin:0 0 18px;max-width:560px}
.hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
.hero-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.hero-chip{padding:.28rem .7rem;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-size:.72rem}
.profile-showcase{
  border-radius:var(--radius);padding:18px;background:linear-gradient(180deg,rgba(255,255,255,.1),rgba(255,255,255,.05));
  border:1px solid rgba(255,255,255,.12);box-shadow:var(--shadow);backdrop-filter:blur(22px);
}
.profile-photo-frame{
  aspect-ratio:4/5;border-radius:24px;overflow:hidden;display:grid;place-items:center;
  background:radial-gradient(ellipse at 50% 80%,rgba(53,227,255,.18),rgba(8,12,28,.9));
}
.profile-photo-frame img{height:92%;width:auto;object-fit:contain;filter:drop-shadow(0 18px 24px rgba(0,0,0,.45))}
.photo-fallback{font-size:4rem;font-weight:900;opacity:.35}
.section{padding:72px 0}
.section-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-end;margin-bottom:28px}
.section-title-en{margin:0;font-size:1.7rem;position:relative;padding-bottom:10px}
.section-title-en::after{content:"";position:absolute;left:0;bottom:0;width:72px;height:3px;border-radius:999px;background:linear-gradient(90deg,var(--cyan),var(--orange),var(--pink))}
.section-head p{margin:0;color:var(--muted);max-width:420px;font-size:.88rem}
.glass{
  background:linear-gradient(180deg,rgba(255,255,255,.1),rgba(255,255,255,.06));
  border:1px solid rgba(255,255,255,.12);box-shadow:var(--shadow);backdrop-filter:blur(22px);
}
.card{border-radius:var(--radius)}
.about-card{padding:28px}
.about-card p{color:#d7e3f6}
.highlight-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:22px}
.highlight{padding:16px;border-radius:18px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}
.highlight strong{display:block;font-size:1.05rem}
.highlight span{color:var(--muted);font-size:.78rem}
.skill-grid,.project-grid,.learning-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.skill-card,.project-card,.learning-card{padding:22px}
.skill-icon{font-size:1.4rem;margin-bottom:8px}
.skill-card h3,.project-card h3,.learning-card h3{margin:.2rem 0 .4rem;font-size:1.05rem}
.skill-card p,.project-card p,.learning-card p{margin:0;color:var(--muted);font-size:.86rem}
.tag-list{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.tag{font-size:.68rem;padding:.15rem .5rem;border-radius:999px;background:rgba(53,227,255,.12);border:1px solid rgba(53,227,255,.25)}
.ev-sn{margin:.45rem 0 0;font-size:.78rem;color:#9fb6d6;line-height:1.55}
.contact-card{width:min(520px,100%);margin:0 auto;padding:24px;text-align:center}
.contact-card a{color:var(--cyan);font-weight:800}
.footer{padding:28px 0 40px;color:#9fb6d6;font-size:.78rem;border-top:1px solid rgba(255,255,255,.08)}
.footer-inner{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
@media (max-width:900px){
  .hero-grid,.skill-grid,.project-grid,.learning-grid,.highlight-grid{grid-template-columns:1fr}
  .nav-links{display:none}
  .hero{padding:36px 0 28px}
  .section{padding:48px 0}
}
@media print{
  body{background:#fff;color:#111}
  .orbs,.noprint,.site-header{display:none}
  .hero-name{-webkit-text-fill-color:#111;color:#111;background:none}
  .glass{box-shadow:none;border:1px solid #ddd}
}
"""


def render_export_html(state: Dict[str, Any]) -> str:
    data = build_growth_export(state)
    pf = data["portfolio"]
    name = data["name"]
    career = pf.get("career_title_ja") or "進路未選択"
    rank = pf.get("rank_ja") or "見習い"
    story = data["story_ja"] or f"{name}の学習ポートフォリオです。"
    skills = data["skills"][:6]
    if not skills:
        skills = [
            {"label_ja": "課題提出"},
            {"label_ja": "試験クリア"},
            {"label_ja": "自己PR"},
        ]
    skill_cards = "".join(
        f"""<article class="skill-card glass card">
          <div class="skill-icon">{_skill_icon(str(s.get('label_ja') or s.get('id') or ''), i)}</div>
          <h3>{_esc(s.get('label_ja') or s.get('id'))}</h3>
          <p>レッスンと試験の記録から身についたスキルです。</p>
        </article>"""
        for i, s in enumerate(skills)
    )
    evidence = data["evidence"][:6]
    if evidence:
        project_cards = "".join(
            f"""<article class="project-card glass card">
              <h3>{_esc(x.get('title_ja') or x.get('id'))}</h3>
              <p>{_esc(x.get('snippet') or '')}</p>
              <div class="tag-list"><span class="tag">{'試験' if x.get('kind')=='exam' else '課題'}</span>
              <span class="tag">{int((x.get('score') or 0)*100)}%</span></div>
            </article>"""
            for x in evidence
        )
    else:
        project_cards = """<article class="project-card glass card">
          <h3>作品はこれから</h3>
          <p>レッスンや試験に自分の言葉で答えると、ここにプロジェクトカードが増えます。</p>
        </article>"""
    exams = data["boss_journey"] or data["exams"]
    if exams:
        learn_cards = "".join(
            f"""<article class="learning-card glass card">
              <h3>{_esc(_boss_label(x.get('boss_type')))} · {_esc(x.get('title_ja') or x.get('id'))}</h3>
              <p>{'合格 ' + str(int((x.get('score') or 0)*100)) + '%' if x.get('score') is not None else 'クリア'} — ボス攻略記</p>
            </article>"""
            for x in exams[:6]
        )
    else:
        learn_cards = """<article class="learning-card glass card">
          <h3>ボス攻略記</h3>
          <p>単元テスト・学期末・認定試験をクリアすると、ここに記録が残ります。</p>
        </article>"""
    pr = "".join(f"<p>{_esc(x)}</p>" for x in (data["self_pr"] or [])[:4]) or "<p>提出物が増えると、ここに自己PRが育ちます。</p>"
    chips = []
    if career and career != "進路未選択":
        chips.append(career)
    if data.get("class_ja"):
        chips.append(str(data["class_ja"]))
    chips.append(f"Lv.{int(data.get('level') or 1)}")
    chips.append(rank)
    chip_html = "".join(f'<span class="hero-chip">{_esc(c)}</span>' for c in chips)
    sprite = data.get("sprite") or ""
    photo = (
        f'<img src="{_esc(sprite)}" alt="{_esc(name)}" />'
        if sprite
        else f'<span class="photo-fallback">{_esc(data["initial"])}</span>'
    )
    n_les = int(pf.get("completed_count") or 0)
    n_boss = int(pf.get("boss_clears") or 0)
    n_ev = len(data["evidence"])
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_esc(name)} | LUNA 学習CV</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&family=Noto+Sans+JP:wght@400;500;700;800&display=swap" rel="stylesheet"/>
  <style>{_SITE_CSS}</style>
</head>
<body>
  <div class="orbs" aria-hidden="true"><span class="orb orb-a"></span><span class="orb orb-b"></span><span class="orb orb-c"></span></div>
  <header class="site-header">
    <div class="container nav">
      <a class="logo" href="#top"><span class="logo-mark">{_esc(data['initial'])}</span><span>LUNA PORTFOLIO</span></a>
      <nav class="nav-links">
        <a href="#about">About</a>
        <a href="#skills">Skills</a>
        <a href="#projects">Projects</a>
        <a href="#learning">Learning</a>
        <a href="#contact">Contact</a>
      </nav>
      <a class="nav-cta" href="#projects">制作物を見る</a>
    </div>
  </header>
  <main>
    <section class="hero" id="top">
      <div class="container hero-grid">
        <div>
          <span class="eyebrow"><span class="live-dot"></span>LUNA Future Skill Quest / 学習CV</span>
          <h1 class="hero-name">{_esc(name)}</h1>
          <p class="hero-title-en">IT Student Portfolio</p>
          <p>{_esc(story)}</p>
          <div class="hero-actions">
            <a class="btn primary" href="#projects">View Projects</a>
            <button class="btn secondary noprint" type="button" onclick="window.print()">印刷 / PDF</button>
          </div>
          <div class="hero-meta">{chip_html}</div>
        </div>
        <div class="profile-showcase">
          <div class="profile-photo-frame">{photo}</div>
        </div>
      </div>
    </section>
    <section class="section" id="about">
      <div class="container">
        <div class="section-head"><div><h2 class="section-title-en">About</h2></div>
          <p>応募書類で伝えた内容と一致するように、学習内容・志向・将来像を整理しています。</p></div>
        <div class="about-card glass card">
          {pr}
          <div class="highlight-grid">
            <div class="highlight"><strong>{n_les}</strong><span>完了レッスン</span></div>
            <div class="highlight"><strong>{n_boss}</strong><span>ボス攻略記</span></div>
            <div class="highlight"><strong>{n_ev}</strong><span>提出エビデンス</span></div>
          </div>
        </div>
      </div>
    </section>
    <section class="section" id="skills">
      <div class="container">
        <div class="section-head"><div><h2 class="section-title-en">Skills</h2></div>
          <p>パーセンテージではなく、実際に学習・実践している内容を中心にまとめています。</p></div>
        <div class="skill-grid">{skill_cards}</div>
      </div>
    </section>
    <section class="section" id="projects">
      <div class="container">
        <div class="section-head"><div><h2 class="section-title-en">Projects</h2></div>
          <p>課題の解答が、そのまま作品カードになります。</p></div>
        <div class="project-grid">{project_cards}</div>
      </div>
    </section>
    <section class="section" id="learning">
      <div class="container">
        <div class="section-head"><div><h2 class="section-title-en">Learning</h2></div>
          <p>試験クリアがボス攻略記として残ります。</p></div>
        <div class="learning-grid">{learn_cards}</div>
      </div>
    </section>
    <section class="section" id="contact">
      <div class="container">
        <div class="section-head"><div><h2 class="section-title-en">Contact</h2></div>
          <p>このページは LUNA が学習記録から自動で組んだ1枚の学習CVです。</p></div>
        <div class="contact-card glass card">
          <p>不具合の報告は <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
        </div>
      </div>
    </section>
  </main>
  <footer class="footer"><div class="container footer-inner">
    <span>© LUNA Future Skill Quest — {_esc(name)} 学習CV</span>
    <span>{_esc(career)} ／ {_esc(rank)}</span>
  </div></footer>
</body></html>
"""
