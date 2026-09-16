# -*- coding: utf-8 -*-
"""Caregiver presence: feel the user's words, still do the job."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from companions import companion_spoken_name, get_companion

_SAD = re.compile(
    r"つらい|辛い|しんど|疲れた|疲れ|落ち込|不安|悲しい|泣|無理|死に|消えたい|"
    r"mệt|buồn|chán|khó quá|tired|sad|anxious|depressed",
    re.I,
)
_JOY = re.compile(
    r"嬉しい|うれしい|楽しい|たのしい|やった|できた|元気|最高|好き|"
    r"vui|giỏi|xong rồi|happy|excited|love it",
    re.I,
)
_ANGER = re.compile(r"怒|むかつ|イライラ|腹立つ|ghét|tức|angry|hate", re.I)
_ASK = re.compile(r"どうすれば|なぜ|教えて|どうして|？|\?|làm sao|why|how", re.I)
_GREET = re.compile(r"こんにちは|おはよう|こんばんは|はじめまして|hello|hi\b", re.I)


def feel_user_text(user_text: str) -> Dict[str, str]:
    """What the companion should *show* after the user speaks."""
    msg = user_text or ""
    if _SAD.search(msg):
        return {"emotion": "sad", "care": "hold"}
    if _ANGER.search(msg):
        return {"emotion": "surprised", "care": "steady"}
    if _JOY.search(msg):
        return {"emotion": "cheer", "care": "celebrate"}
    if _GREET.search(msg):
        return {"emotion": "wave", "care": "hello"}
    if _ASK.search(msg):
        return {"emotion": "think", "care": "guide"}
    return {"emotion": "talk", "care": "listen"}


def _who(user: Dict[str, Any]) -> str:
    raw = str((user or {}).get("user_display_name") or "").strip()
    raw = re.sub(r"(様|さん|くん|君|ちゃん)$", "", raw).strip()
    if raw in ("", "お客", "お客様", "お客さま", "あなた", "冒険者", "学習者"):
        return ""
    cid = str((user or {}).get("companion_id") or "")
    animal = cid in ("hachi", "momo", "taro", "ponta")
    return f"{raw}ちゃん" if animal else f"{raw}さん"


def _cid(user: Dict[str, Any]) -> str:
    return get_companion((user or {}).get("companion_id")).get("id") or "luna"


def crisis_script(user: Dict[str, Any]) -> Dict[str, Any]:
    """60s rescue lines in the selected companion's voice."""
    cid = _cid(user)
    who = _who(user)
    prefix = f"{who}、" if who else ""
    name = companion_spoken_name(user)
    voices = {
        "luna": {
            "lead": f"{prefix}いまは授業じゃない。私がそばにいる。60秒だけ、一緒に戻ろう。",
            "breathe": "いい子。鼻から4、止めて2、口から6。私が見てるから、呼吸だけでいい。",
            "ground": "足の裏、椅子、今の音。世界はまだここにあるよ。",
            "one": "次は水を一杯か、目を閉じる。それ以外は、先生が預かる。",
            "done": "よく戻ってきた。家族や親友に、いまかけていい。急がなくていい。",
        },
        "luno": {
            "lead": f"{prefix}ルノ、にげないよ。60秒だけ、手つないで戻ろ？",
            "breathe": "えへへ、いっしょに吸って…吐いて。ルノが数えるから。",
            "ground": "足、さわって。椅子、あるでしょ。ルノもいるよ。",
            "one": "お水が、目つぶる。どっちか一つでいい。ほかはやらなくていい。",
            "done": "おかえり。えらい。家族や親友、よべるよ。",
        },
        "ren": {
            "lead": f"{prefix}俺がいる。60秒、俺のペースで戻るぞ。",
            "breathe": "吸って4、止めて2、吐いて6。考えなくていい、身体だけ。",
            "ground": "足の裏を床に置け。椅子の感触。音を一つ。俺も聞いてる。",
            "one": "水か、目を閉じる。先輩命令だ。それ以外は後回し。",
            "done": "戻ったな。よくやった。家族や親友に、かけていい。",
        },
        "hachi": {
            "lead": f"{prefix}わんっ…ハチ、そばにいる。60秒、一緒。",
            "breathe": "ふーっ、ふーっ。ハチもする。一緒に息して。",
            "ground": "足、トントン。床がある。ハチの声も聞こえる。",
            "one": "お水、または目をとじる。わんっ、それだけ。",
            "done": "おかえりだよ。なでなで。家族や親友にかけていいよ。",
        },
        "momo": {
            "lead": f"{prefix}にゃあ。急がなくていい。60秒、モモがいる。",
            "breathe": "ゆっくり吸って。吐いて。猫は急がない。",
            "ground": "足のうら。椅子。音、一つ。世界はここ。",
            "one": "水か、目をとじる。ほかはあとでいい。",
            "done": "戻ったね。モモ、ここにいる。家族や親友にかけていいよ。",
        },
        "taro": {
            "lead": f"{prefix}もぐもぐ…タロもいる。60秒、ゆっくり戻ろう。",
            "breathe": "吸って…吐いて。急がなくていいよ。",
            "ground": "足。椅子。音。タロも聞こえてる。",
            "one": "お水か、目をとじる。それだけでいい。",
            "done": "おかえり。もぐもぐ…家族や親友にかけていいよ。",
        },
        "ponta": {
            "lead": f"{prefix}ぽんっ。逃げない。60秒、ポンタがついてる。",
            "breathe": "吸って、吐いて。いたずら禁止、いまは息だけ。",
            "ground": "足、床、音。ほら、世界まだある。",
            "one": "水か、目をとじる。ほかの任務はキャンセル。",
            "done": "おかえりっ。えらい。家族や親友にかけていいよ。",
        },
    }
    v = voices.get(cid) or voices["luna"]
    return {
        "companion_id": cid,
        "companion_name": name,
        "lead_ja": v["lead"],
        "done_ja": v["done"],
        "steps": [
            {"id": "breathe", "sec": 20, "title_ja": "呼吸", "line_ja": v["breathe"], "emotion": "sad"},
            {"id": "ground", "sec": 20, "title_ja": "接地", "line_ja": v["ground"], "emotion": "think"},
            {"id": "one", "sec": 20, "title_ja": "ひとつだけ", "line_ja": v["one"], "emotion": "happy"},
        ],
    }


def hud_line(user: Dict[str, Any], event: str, extra: str = "") -> Dict[str, str]:
    cid = _cid(user)
    name = companion_spoken_name(user)
    table = {
        "follow": {
            "luna": "見てるよ。続けて。",
            "luno": "ルノ、ついてくよ〜。",
            "ren": "俺が後ろにいる。",
            "hachi": "わんっ、ついてく！",
            "momo": "にゃあ。そばにいる。",
            "taro": "もぐ…ついてくよ。",
            "ponta": "ぽんっ、護衛開始。",
        },
        "suspect": {
            "luna": "今、逃げた？戻ってきたなら、続きから。",
            "luno": "ちょっと！いまいなくなったよね？怪しい〜。",
            "ren": "席を外したな。戻ったなら、やれ。",
            "hachi": "わんっ？いなくなった。戻った？",
            "momo": "……いなくなった。戻ったなら、続き。",
            "taro": "もぐ？いなくなった。戻ったね。",
            "ponta": "ふぅん、抜け駆け？怪しいぞ。",
        },
        "cheer": {
            "luna": "その打ち込み、届いてる。",
            "luno": "それっ、それっ！攻撃〜！",
            "ren": "いい。そのまま押せ。",
            "hachi": "わんっ！がんばれ！",
            "momo": "いい爪あと。続けて。",
            "taro": "もぐもぐ…いいよ。",
            "ponta": "ぽんっ！クリティカル狙い！",
        },
        "win": {
            "luna": "よくやった。今日の自分に勝った。",
            "luno": "やったー！えらいえらい！",
            "ren": "勝ちだ。誇っていい。",
            "hachi": "わんっ！勝った！なでなで！",
            "momo": "にゃあ。よく勝った。",
            "taro": "もぐ…勝ったね。えらい。",
            "ponta": "ぽんっ！ボス沈没！",
        },
        "rest": {
            "luna": "長く戦った。一度、目を休めて。",
            "luno": "ちょっと休憩しよ？ルノも眠い。",
            "ren": "集中は続くが、体は限界だ。休め。",
            "hachi": "わん…お水の時間だよ。",
            "momo": "猫は昼寝する。あなたも、少し。",
            "taro": "もぐもぐ休憩。いいよ。",
            "ponta": "スタミナ切れ注意。一回休め。",
        },
        "idle": {
            "luna": "手が止まってる。一行でいい、書いて。",
            "luno": "えー、書いてよ〜。ルノ待ってる。",
            "ren": "止まっている。動け。",
            "hachi": "わん？書いて？",
            "momo": "……まだ？一行でいい。",
            "taro": "もぐ…書いてみよ。",
            "ponta": "サボり発見。一行だけ打て。",
        },
    }
    pack = table.get(event) or table["follow"]
    line = pack.get(cid) or pack["luna"]
    if extra:
        line = line + " " + extra
    emotion = {
        "follow": "happy",
        "suspect": "think",
        "cheer": "cheer",
        "win": "cheer",
        "rest": "sad",
        "idle": "think",
        "lose": "sad",
    }.get(event, "happy")
    return {"line_ja": line, "emotion": emotion, "name": name, "companion_id": cid}


def exam_fail_advice(user: Dict[str, Any], weak_titles: List[str], score: float) -> Dict[str, str]:
    titles = [t for t in (weak_titles or []) if t][:3]
    topic = "、".join(titles) if titles else "足りなかった単元"
    cid = _cid(user)
    name = companion_spoken_name(user)
    pct = int(round((score or 0) * 100))
    lines = {
        "luna": f"負けは消えない。でも進捗は残ってる。今回は「{topic}」が薄い。そこをノート1枚だけ復習して、もう一度来て。",
        "luno": f"負けちゃった…でも消えてないよ！「{topic}」をもう一回いっしょに見よ？スコア{pct}%。次いける。",
        "ren": f"沈んだな。進捗は残す。弱点は「{topic}」。そこだけやり直せ。スコア{pct}%。",
        "hachi": f"わん…負け。でもハチいる。「{topic}」おさらいして、また来て。",
        "momo": f"にゃあ。負けた。消えてないよ。「{topic}」を、ゆっくり復習。",
        "taro": f"もぐ…負けた。でも残ってる。「{topic}」を、ひと口復習しよ。",
        "ponta": f"ぽんっ、ダウン。でもセーブは生きてる。「{topic}」を攻略して再戦だ。",
    }
    return {
        "line_ja": lines.get(cid) or lines["luna"],
        "emotion": "sad",
        "name": name,
        "weak_titles": titles,
        "score_pct": pct,
    }


def exam_win_line(user: Dict[str, Any], label: str = "") -> Dict[str, str]:
    pack = hud_line(user, "win")
    if label:
        pack["line_ja"] = pack["line_ja"] + f" {label}"
    return pack


def feel_prompt_block(user_text: str) -> str:
    felt = feel_user_text(user_text)
    return (
        "USER FEELING RIGHT NOW: "
        f"{felt['emotion']} / care={felt['care']}. "
        "Show that emotion on your face. Still do the job: "
        "record health/money/schedule if mentioned, then one next step. "
        "Do not lecture. Do not diagnose. Caregiver, not manager."
    )
