"""Expand career curricula into longer, career-realistic learning paths."""
from __future__ import annotations

import copy
from typing import Any, Dict, List

_CAREER_TARGETS: Dict[str, Dict[str, Any]] = {
    "software_engineer": {"expand": False},
    "ui_designer": {"stages": 8, "per_stage": 5, "difficulty": 3},
    "nurse": {"stages": 8, "per_stage": 5, "difficulty": 4},
    "teacher": {"stages": 8, "per_stage": 5, "difficulty": 3},
    "data_analyst": {"stages": 9, "per_stage": 5, "difficulty": 4},
    "game_creator": {"stages": 8, "per_stage": 5, "difficulty": 3},
    "architect": {"stages": 9, "per_stage": 5, "difficulty": 4},
    "marketer": {"stages": 7, "per_stage": 4, "difficulty": 2},
    "researcher": {"stages": 10, "per_stage": 5, "difficulty": 5},
    "chef": {"stages": 8, "per_stage": 5, "difficulty": 3},
    "pilot": {"stages": 9, "per_stage": 5, "difficulty": 5},
    "entrepreneur": {"stages": 8, "per_stage": 5, "difficulty": 4},
}

_DEFAULT_TARGET = {"stages": 7, "per_stage": 5, "difficulty": 3}

_STAGE_THEMES: Dict[str, List[Dict[str, str]]] = {
    "it_engineering": [
        {"label_ja": "学習の土台", "theme_ja": "習慣・論理"},
        {"label_ja": "プログラミング入門", "theme_ja": "変数・制御"},
        {"label_ja": "Web基礎", "theme_ja": "HTML/CSS/JS"},
        {"label_ja": "アルゴリズムの森", "theme_ja": "データ構造"},
        {"label_ja": "実践プロジェクト", "theme_ja": "小さく作る"},
        {"label_ja": "品質とツール", "theme_ja": "Git・テスト"},
        {"label_ja": "フロント実装", "theme_ja": "UI・状態"},
        {"label_ja": "バックエンド", "theme_ja": "API・DB"},
        {"label_ja": "チーム開発", "theme_ja": "レビュー・協業"},
        {"label_ja": "キャリアの城", "theme_ja": "作品・就活"},
    ],
    "design_creative": [
        {"label_ja": "デザインの目", "theme_ja": "観察"},
        {"label_ja": "UIの基礎", "theme_ja": "レイアウト"},
        {"label_ja": "UXの思考", "theme_ja": "ユーザー"},
        {"label_ja": "ビジュアル表現", "theme_ja": "色・タイポ"},
        {"label_ja": "プロトタイプ", "theme_ja": "モック"},
        {"label_ja": "ユーザビリティ", "theme_ja": "テスト"},
        {"label_ja": "デザインシステム", "theme_ja": "一貫性"},
        {"label_ja": "ポートフォリオ", "theme_ja": "作品"},
    ],
    "care_helping": [
        {"label_ja": "ケアの心構え", "theme_ja": "共感"},
        {"label_ja": "基礎医学", "theme_ja": "体のしくみ"},
        {"label_ja": "観察と記録", "theme_ja": "バイタル"},
        {"label_ja": "現場実習①", "theme_ja": "基本技術"},
        {"label_ja": "チーム医療", "theme_ja": "連携"},
        {"label_ja": "患者コミュニケーション", "theme_ja": "伝え方"},
        {"label_ja": "現場実習②", "theme_ja": "応用"},
        {"label_ja": "国家試験の丘", "theme_ja": "総合"},
    ],
    "education": [
        {"label_ja": "教える準備", "theme_ja": "学び方"},
        {"label_ja": "授業設計", "theme_ja": "目標"},
        {"label_ja": "教材づくり", "theme_ja": "資料"},
        {"label_ja": "教室運営", "theme_ja": "雰囲気"},
        {"label_ja": "個別支援", "theme_ja": "多様性"},
        {"label_ja": "評価とFB", "theme_ja": "成長"},
        {"label_ja": "教育実習", "theme_ja": "現場"},
        {"label_ja": "教員の未来", "theme_ja": "キャリア"},
    ],
    "hands_on_making": [
        {"label_ja": "職人の基礎", "theme_ja": "安全"},
        {"label_ja": "材料と技法", "theme_ja": "基本"},
        {"label_ja": "設計思考", "theme_ja": "計画"},
        {"label_ja": "制作実習①", "theme_ja": "実践"},
        {"label_ja": "品質管理", "theme_ja": "仕上げ"},
        {"label_ja": "制作実習②", "theme_ja": "応用"},
        {"label_ja": "現場体験", "theme_ja": "プロ"},
        {"label_ja": "作品・資格", "theme_ja": "ゴール"},
    ],
    "business_social": [
        {"label_ja": "市場理解", "theme_ja": "リサーチ"},
        {"label_ja": "伝える力", "theme_ja": "SNS"},
        {"label_ja": "企画基礎", "theme_ja": "戦略"},
        {"label_ja": "データ改善", "theme_ja": "分析"},
        {"label_ja": "キャンペーン", "theme_ja": "実行"},
        {"label_ja": "ブランド", "theme_ja": "一貫性"},
        {"label_ja": "キャリア実践", "theme_ja": "成果"},
    ],
    "science_research": [
        {"label_ja": "探究の始まり", "theme_ja": "問い"},
        {"label_ja": "文献と仮説", "theme_ja": "調査"},
        {"label_ja": "実験設計", "theme_ja": "方法"},
        {"label_ja": "データ記録", "theme_ja": "観察"},
        {"label_ja": "分析", "theme_ja": "統計"},
        {"label_ja": "論文・発表", "theme_ja": "まとめ"},
        {"label_ja": "研究倫理", "theme_ja": "責任"},
        {"label_ja": "応用研究", "theme_ja": "発展"},
        {"label_ja": "研究者の道", "theme_ja": "キャリア"},
    ],
    "default": [
        {"label_ja": "始まりの平原", "theme_ja": "導入"},
        {"label_ja": "学習の森", "theme_ja": "基礎"},
        {"label_ja": "試練の丘陵", "theme_ja": "実践"},
        {"label_ja": "知恵の谷", "theme_ja": "応用"},
        {"label_ja": "協力の橋", "theme_ja": "チーム"},
        {"label_ja": "専門の塔", "theme_ja": "深化"},
        {"label_ja": "キャリアの丘", "theme_ja": "総仕上げ"},
    ],
}

_LESSON_VERBS = ["を学ぶ", "の基礎", "を実践", "チャレンジ", "の演習", "を深掘り", "まとめ", "復習"]


def _cluster_themes(cluster_id: str) -> List[Dict[str, str]]:
    return list(_STAGE_THEMES.get(cluster_id) or _STAGE_THEMES["default"])


def _lesson_title(stage_label: str, n: int, theme: str) -> str:
    return f"{stage_label}：{theme}{_LESSON_VERBS[(n - 1) % len(_LESSON_VERBS)]}"


def _boss_for_stage(stage_order: int, total_stages: int) -> str:
    if stage_order >= total_stages:
        return "career_final"
    if stage_order % 3 == 0:
        return "monthly"
    if stage_order % 2 == 0:
        return "weekly"
    return "none"


def expand_curriculum(cur: Dict[str, Any], career_id: str, cluster_id: str) -> Dict[str, Any]:
    cfg = _CAREER_TARGETS.get(career_id, _DEFAULT_TARGET)
    if cfg.get("expand") is False:
        out = copy.deepcopy(cur)
        out["_expanded"] = True
        return out

    target_stages = int(cfg.get("stages") or 7)
    per_stage = int(cfg.get("per_stage") or 5)
    difficulty = int(cfg.get("difficulty") or 3)
    themes = _cluster_themes(cluster_id)
    if len(themes) < target_stages:
        themes = themes + [themes[-1]] * (target_stages - len(themes))
    themes = themes[:target_stages]

    prefix = career_id.replace("_", "")[:10]
    skills = list(cur.get("skills") or [{"id": f"{prefix}_sk1", "label_ja": "専門スキル"}])
    orig_titles = [str(x.get("title_ja") or "") for x in (cur.get("lessons") or []) if x.get("title_ja")]
    ti = 0

    stages: List[Dict[str, Any]] = []
    lessons: List[Dict[str, Any]] = []

    for i, th in enumerate(themes, start=1):
        sid = f"{prefix}_xs{i}"
        stages.append({"id": sid, "order": i, "label_ja": th["label_ja"], "theme_ja": th["theme_ja"]})
        for n in range(1, per_stage + 1):
            lid = f"{prefix}_xl{i}_{n}"
            title = orig_titles[ti] if ti < len(orig_titles) else _lesson_title(th["label_ja"], n, th["theme_ja"])
            ti += 1
            boss = _boss_for_stage(i, target_stages) if n == per_stage else "none"
            exp = 10 + difficulty * 2 + i + n + (14 if boss != "none" else 0)
            lessons.append(
                {
                    "id": lid,
                    "stage_id": sid,
                    "title_ja": title,
                    "skill_ids": [skills[(i + n) % len(skills)]["id"]],
                    "exp": exp,
                    "difficulty": min(5, difficulty + (i - 1) // 2),
                    "gear_drop": None,
                    "boss_type": boss,
                }
            )

    return {
        "career_id": career_id,
        "stages": stages,
        "skills": skills,
        "lessons": lessons,
        "_expanded": True,
        "_difficulty": difficulty,
    }


def should_expand(career_id: str, cur: Dict[str, Any]) -> bool:
    if cur.get("_expanded"):
        return False
    cfg = _CAREER_TARGETS.get(career_id, _DEFAULT_TARGET)
    if cfg.get("expand") is False:
        return False
    target = int(cfg.get("stages") or 7) * int(cfg.get("per_stage") or 5)
    have = len(cur.get("lessons") or [])
    return have < int(target * 0.85)
